from __future__ import annotations

import uuid

from fastapi import Depends, FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agent import config
from agent.envelope import AgentError, envelope
from agent.features.findbook.service import FindBookService
from agent.features.knowledge_map.s2_cache import S2Cache
from agent.features.knowledge_map.semantic_scholar import SemanticScholarClient
from agent.features.knowledge_map.service import KnowledgeMapService
from agent.features.seat_predict.service import SeatPredictService
from agent.service_client import ServiceClient, ServiceError, ServiceUnavailable

app = FastAPI(title="library-patch agent")

# web/ 前端从 :5173 直连 :8000, 放开跨域 (本地/演示环境)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_service_client = ServiceClient(
    base_url=config.SERVICE_BASE_URL,
    internal_token=config.INTERNAL_TOKEN or None,
)
_findbook_service: FindBookService | None = None
_knowledge_service: KnowledgeMapService | None = None
_seat_service: SeatPredictService | None = None
_agent_loop = None


@app.on_event("startup")
def _assemble_services() -> None:
    global _findbook_service, _knowledge_service, _seat_service, _agent_loop
    try:
        from agent.core.agent_loop import AgentLoop  # noqa: PLC0415
        from agent.core.llm import LLMClient  # noqa: PLC0415
        from agent.core.planner import Planner  # noqa: PLC0415
        from agent.memory.extractor import MemoryExtractor  # noqa: PLC0415
        from agent.memory.retriever import MemoryRetriever  # noqa: PLC0415
        from agent.memory.store import MemoryStore  # noqa: PLC0415
    except ImportError:
        # B has not delivered agent.core yet; routes still function via dependency_overrides in tests.
        return

    llm = LLMClient(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY, model=config.LLM_MODEL)
    store = MemoryStore(config.MEMORY_DB_PATH)
    _agent_loop = AgentLoop(MemoryRetriever(store), Planner(llm), store, MemoryExtractor(llm))

    # 启动配置摘要(隐藏 key), 便于现场确认配置是否生效
    masked = (config.LLM_API_KEY[:4] + "***") if config.LLM_API_KEY else "(未配置,LLM 功能降级)"
    print(
        f"[config] SERVICE_BASE_URL={config.SERVICE_BASE_URL} "
        f"LLM_BASE_URL={config.LLM_BASE_URL or '(openai 默认)'} LLM_MODEL={config.LLM_MODEL} "
        f"LLM_API_KEY={masked} SEATS_DB={config.SEATS_DB_PATH} MEMORY_DB={config.MEMORY_DB_PATH}"
    )
    _findbook_service = FindBookService(_agent_loop, _service_client)
    _knowledge_service = KnowledgeMapService(_agent_loop, SemanticScholarClient(), S2Cache())
    _seat_service = SeatPredictService(
        _agent_loop, _service_client, seats_db_path=config.SEATS_DB_PATH
    )


def get_findbook_service() -> FindBookService:
    if _findbook_service is None:
        raise AgentError(60001, "service not ready (B layer pending)")
    return _findbook_service


def get_knowledge_service() -> KnowledgeMapService:
    if _knowledge_service is None:
        raise AgentError(60001, "service not ready (B layer pending)")
    return _knowledge_service


def get_seat_service() -> SeatPredictService:
    if _seat_service is None:
        raise AgentError(60001, "service not ready (B layer pending)")
    return _seat_service


def _llm_available() -> bool:
    """LLM 是否可用——反馈接口据此告诉前端记忆是否真的沉淀了。"""
    return bool(
        _agent_loop is not None
        and getattr(getattr(_agent_loop, "planner", None), "llm", None) is not None
        and _agent_loop.planner.llm.available
    )


def _user_id(x_user_id: str | None = Header(default=None, alias="X-User-Id")) -> str:
    return x_user_id or "default"


def _trace_id(x_trace_id: str | None = Header(default=None, alias="X-Trace-Id")) -> str:
    return x_trace_id or uuid.uuid4().hex[:8]


@app.exception_handler(AgentError)
async def _agent_error_handler(request: Request, exc: AgentError):
    return JSONResponse(status_code=200, content=envelope(exc.code, exc.msg))


@app.exception_handler(ServiceError)
async def _service_error_handler(request: Request, exc: ServiceError):
    return JSONResponse(status_code=200, content=envelope(exc.code, exc.msg))


@app.exception_handler(ServiceUnavailable)
async def _service_unavailable_handler(request: Request, exc: ServiceUnavailable):
    return JSONResponse(status_code=200, content=envelope(50001, "data service unavailable"))


@app.post("/findbook/search")
async def findbook_search(
    body: dict,
    user_id: str = Depends(_user_id),
    trace_id: str = Depends(_trace_id),
    service: FindBookService = Depends(get_findbook_service),
):
    result = await service.find(
        query=body["query"],
        page=body.get("page", 1),
        page_size=body.get("page_size", 10),
        user_id=user_id,
        trace_id=trace_id,
    )
    data = result.output if hasattr(result, "output") else result
    # 透出 planner 的偏好说明, 让"记忆生效"在 UI 上可见(无 LLM/无记忆时为空串)
    if isinstance(data, dict):
        data = {**data, "plan_note": getattr(result, "plan_note", "") or ""}
    return envelope(0, "ok", data)


@app.post("/findbook/feedback")
async def findbook_feedback(
    body: dict,
    user_id: str = Depends(_user_id),
    trace_id: str = Depends(_trace_id),
    service: FindBookService = Depends(get_findbook_service),
):
    ids = await service.feedback(feedback=body["feedback"], user_id=user_id, trace_id=trace_id)
    return envelope(0, "ok", {"memory_ids": ids, "llm_available": _llm_available()})


@app.post("/knowledge/search")
async def knowledge_search(
    body: dict,
    service: KnowledgeMapService = Depends(get_knowledge_service),
):
    return envelope(0, "ok", await service.search_papers(body["query"]))


@app.post("/knowledge/graph")
async def knowledge_graph(
    body: dict,
    user_id: str = Depends(_user_id),
    trace_id: str = Depends(_trace_id),
    service: KnowledgeMapService = Depends(get_knowledge_service),
):
    result = await service.build_graph(paper_id=body["paper_id"], user_id=user_id, trace_id=trace_id)
    return envelope(0, "ok", result.output if hasattr(result, "output") else result)


@app.post("/knowledge/summarize")
async def knowledge_summarize(
    body: dict,
    user_id: str = Depends(_user_id),
    trace_id: str = Depends(_trace_id),
    service: KnowledgeMapService = Depends(get_knowledge_service),
):
    result = await service.summarize(paper_id=body["paper_id"], user_id=user_id, trace_id=trace_id)
    return envelope(0, "ok", result.output if hasattr(result, "output") else result)


@app.post("/seat/predict")
async def seat_predict(
    body: dict,
    user_id: str = Depends(_user_id),
    trace_id: str = Depends(_trace_id),
    service: SeatPredictService = Depends(get_seat_service),
):
    result = await service.predict(
        weekday=body["weekday"], hour=body["hour"], user_id=user_id, trace_id=trace_id,
    )
    return envelope(0, "ok", result.output if hasattr(result, "output") else result)


@app.post("/seat/map")
async def seat_map(
    body: dict,
    trace_id: str = Depends(_trace_id),
    service: SeatPredictService = Depends(get_seat_service),
):
    return envelope(0, "ok", await service.seat_map(body["map_id"], trace_id))


@app.post("/seat/feedback")
async def seat_feedback(
    body: dict,
    user_id: str = Depends(_user_id),
    trace_id: str = Depends(_trace_id),
    service: SeatPredictService = Depends(get_seat_service),
):
    ids = await service.feedback(feedback=body["feedback"], user_id=user_id, trace_id=trace_id)
    return envelope(0, "ok", {"memory_ids": ids, "llm_available": _llm_available()})


@app.post("/memory/feedback")
async def memory_feedback(
    body: dict,
    user_id: str = Depends(_user_id),
    trace_id: str = Depends(_trace_id),
):
    if _agent_loop is None:
        raise AgentError(60001, "memory service not ready (B layer pending)")
    ids = await _agent_loop.record_feedback(
        feedback=body["feedback"],
        user_id=user_id,
        task_context=body.get("task_context", ""),
        trace_id=trace_id,
    )
    return envelope(0, "ok", {"memory_ids": ids, "llm_available": _llm_available()})


@app.get("/health")
async def health(trace_id: str = Depends(_trace_id)):
    agent_status = "ok"
    java_status: dict = {}
    try:
        java_status = await _service_client.health(trace_id)
    except (ServiceError, ServiceUnavailable):
        java_status = {"status": "unavailable"}
    return envelope(0, "ok", {"agent": agent_status, "java": java_status})

