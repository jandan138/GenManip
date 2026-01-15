import asyncio
from fastapi import FastAPI, APIRouter, Request, HTTPException, Response
import traceback
import uvicorn
import pickle


class EvalServer:
    """
    Server class for Eval service.
    Uses FastAPI to create a web server that handles evaluation requests.

    Args:
        host (str): Host address for the server.
        port (int): Port number for the server.
        workers (int): Number of worker processes for the server.

    Routes:
        - /step: POST request to perform a step in the evaluation.
        - /reset: POST request to reset the evaluation environment.
        - /kill: POST request to kill specified workers.
        - /create_workers: create workers by id
        - /load_config: load a new task config

    Functions:
        - register_worker_pool(pool): Register a worker pool to handle evaluation tasks.
        - run(): Start the FastAPI server.
    """

    def __init__(self, host: str, port: int, workers: int):
        self.host = host
        self.port = port
        self.workers = workers
        self.app = FastAPI(title="Eval Service")
        self._router = APIRouter()
        self._register_routes()
        self.app.include_router(self._router)

    def _register_routes(self):
        route_config = [
            ("/step", self.step, ["POST"]),
            ("/kill", self.kill, ["POST"]),
            ("/reset", self.reset, ["POST"]),
            ("/create_workers", self.create_workers, ["POST"]),
            ("/load_config", self.load_config, ["POST"]),
        ]

        for path, handler, methods in route_config:
            self._router.add_api_route(
                path=path,
                endpoint=handler,
                methods=methods,
            )

    # ================= Registered routes =================
    async def step(self, request: Request) -> Response:
        """
        step vec env by the action, return binary obs/data

        Args:
            request.body(): pickled action_dict

        Return:
            pickled obs_dict / data_dict
                {
                    worker_id:
                    {
                        'obs': ...,
                        'sr': ...,
                    }
                }
        """
        pool = request.app.state.pool
        try:
            raw = await request.body()
            try:
                action_dict = pickle.loads(raw)
            except Exception as e:
                raise HTTPException(
                    status_code=400, detail=f"Invalid pickle in request body: {e}"
                )

            response_data = await asyncio.to_thread(pool.step, action_dict)

            # return pickled response_data
            blob = pickle.dumps(response_data, protocol=pickle.HIGHEST_PROTOCOL)
            return Response(content=blob, media_type="application/octet-stream")

        except HTTPException:
            raise
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))

    async def kill(self, request: Request):
        """
        body: {"data": {"worker_ids": [...]}}
        """
        pool = request.app.state.pool
        try:
            body = await request.json()
            worker_ids = body["data"]["worker_ids"]
            await asyncio.to_thread(pool.kill_workers, worker_ids)
            return {"data": {"success": True}}
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))

    async def reset(self, request: Request) -> Response:
        """
        reset in gym style

        Args:
            request: pickled {"worker_ids": [...]}

        Return:
            pickled obs_dict
        """
        pool = request.app.state.pool
        try:
            raw = await request.body()
            if raw:
                try:
                    req_data = pickle.loads(raw)
                except Exception as e:
                    raise HTTPException(
                        status_code=400, detail=f"Invalid pickle in reset body: {e}"
                    )
                worker_ids = req_data.get("worker_ids", None)
            else:
                worker_ids = None

            obs_dict = await asyncio.to_thread(pool.reset, worker_ids)

            blob = pickle.dumps(obs_dict, protocol=pickle.HIGHEST_PROTOCOL)
            return Response(content=blob, media_type="application/octet-stream")

        except HTTPException:
            raise
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))

    async def create_workers(self, request: Request):
        """
        body: {"data": {"worker_ids": [...]}}
        """
        pool = request.app.state.pool
        try:
            body = await request.json()
            worker_ids = body["data"]["worker_ids"]
            await asyncio.to_thread(pool.create_workers, worker_ids)
            return {"data": {"success": True}}
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))
        
    async def load_config(self, request: Request):
        """
        body: {"data": {"config_path": ...}}
        """
        pool = request.app.state.pool
        try:
            body = await request.json()
            config_path = body["data"]["config_path"]
            await asyncio.to_thread(pool.load_config, config_path)
            return {"data": {"success": True}}
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))

    # ================= Server functions =================
    def register_worker_pool(self, pool):
        self.app.state.pool = pool

    def run(self):
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            workers=self.workers,
        )
