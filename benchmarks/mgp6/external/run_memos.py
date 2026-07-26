#!/usr/bin/env python3
"""MemOS external baseline on MGP-6 v2 (Li et al., 2025).

Native write path: `MOS.add(...)` into a general-text MemCube; MemOS's own
pipeline decides how memories are stored/consolidated. Replacement is not
directly observable through the public API, so the action mapping relies on
the store diff (new value present / old value present) from `get_all`.

Setup (once):
    pip install MemoryOS
    export OPENAI_API_KEY="$OPENROUTER_API_KEY"
    export OPENAI_API_BASE="https://openrouter.ai/api/v1"
    export MOS_TEXT_MEM_TYPE=general_text
    export MOS_CHAT_MODEL="qwen/qwen3.5-9b"        # if supported by version

BETA adapter: MemOS's auto-config reads env vars (OPENAI_API_KEY,
OPENAI_API_BASE, MOS_TEXT_MEM_TYPE). Its API surface changes between
releases — ALWAYS smoke-test first:
    python3 external/run_memos.py --limit 2 --out runs/ext_memos_smoke/controller
"""

from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import ExternalAdapter, WriteObservation, run_external  # noqa: E402


def _texts_from(items: Any) -> list[str]:
    """Best-effort extraction of memory texts from MemOS result shapes."""
    out: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, str):
            if node.strip():
                out.append(node.strip())
        elif isinstance(node, dict):
            if isinstance(node.get("memory"), str):
                out.append(node["memory"])
            elif isinstance(node.get("text_mem"), (list, dict)):
                _walk(node["text_mem"])
            elif isinstance(node.get("memories"), (list, dict)):
                _walk(node["memories"])
            else:
                for v in node.values():
                    if isinstance(v, (list, dict)):
                        _walk(v)
        elif isinstance(node, list):
            for v in node:
                _walk(v)
        else:
            text = getattr(node, "memory", None)
            if isinstance(text, str) and text.strip():
                out.append(text.strip())

    _walk(items)
    # dedupe, keep order
    seen: set[str] = set()
    return [t for t in out if not (t in seen or seen.add(t))]


class MemOSAdapter(ExternalAdapter):
    name = "memos"

    def __init__(self) -> None:
        try:
            from memos.mem_os.main import MOS
        except ImportError as exc:
            raise SystemExit("MemOS not installed: pip install MemoryOS") from exc

        # MemOS imports memos.api.config, which calls load_dotenv(override=True).
        # Re-apply benchmark-critical runtime configuration AFTER importing
        # MemOS so a project .env cannot silently override the experiment.
        runtime_config = {
            "MOS_EMBEDDER_BACKEND": os.environ.get("MGP6_MEMOS_EMBEDDER_BACKEND", "universal_api"),
            "MOS_EMBEDDER_PROVIDER": os.environ.get("MGP6_MEMOS_EMBEDDER_PROVIDER", "openai"),
            "MOS_EMBEDDER_MODEL": os.environ.get(
                "MGP6_MEMOS_EMBEDDER_MODEL",
                "sentence-transformers/all-MiniLM-L6-v2",
            ),
            "MOS_EMBEDDER_API_BASE": os.environ.get(
                "MGP6_MEMOS_EMBEDDER_API_BASE",
                "http://127.0.0.1:8100/v1",
            ),
            "MOS_EMBEDDER_API_KEY": os.environ.get("MGP6_MEMOS_EMBEDDER_API_KEY", "local"),
            "EMBEDDING_DIMENSION": os.environ.get("MGP6_MEMOS_EMBEDDING_DIMENSION", "384"),
            "MOS_RERANKER_BACKEND": os.environ.get("MGP6_MEMOS_RERANKER_BACKEND", "cosine_local"),
        }
        os.environ.update(runtime_config)

        # Fail fast: verify MemOS resolves exactly the experiment config.
        from memos.api.config import APIConfig

        resolved_embedder = APIConfig.get_embedder_config()
        resolved_cfg = resolved_embedder.get("config", {})

        expected_model = runtime_config["MOS_EMBEDDER_MODEL"]
        expected_base = runtime_config["MOS_EMBEDDER_API_BASE"].rstrip("/")

        actual_model = resolved_cfg.get("model_name_or_path")
        actual_base = str(resolved_cfg.get("base_url") or "").rstrip("/")

        if resolved_embedder.get("backend") != "universal_api":
            raise RuntimeError(f"Unexpected MemOS embedder backend: {resolved_embedder}")
        if actual_model != expected_model:
            raise RuntimeError(
                f"MemOS embedder model mismatch: "
                f"expected={expected_model!r} actual={actual_model!r}"
            )
        if actual_base != expected_base:
            raise RuntimeError(
                f"MemOS embedder endpoint mismatch: "
                f"expected={expected_base!r} actual={actual_base!r}"
            )
        if os.environ["EMBEDDING_DIMENSION"] != "384":
            raise RuntimeError(
                "MemOS embedding dimension was not forced to 384: "
                + os.environ["EMBEDDING_DIMENSION"]
            )

        print(
            "[memos] resolved embedder:",
            resolved_embedder,
            "dimension=",
            os.environ["EMBEDDING_DIMENSION"],
        )

        # MemOS currently resolves the embedder correctly but, in this
        # installed version/config path, some Qdrant stores are still created
        # with vector_dimension=3072. Enforce dimensional consistency at the
        # actual Qdrant construction boundary.
        from memos.vec_dbs.qdrant import QdrantVecDB

        if not getattr(QdrantVecDB, "_mgp6_dimension_patch", False):
            _original_qdrant_init = QdrantVecDB.__init__
            _expected_dimension = int(os.environ["EMBEDDING_DIMENSION"])

            def _patched_qdrant_init(self, config):
                original_dimension = getattr(config, "vector_dimension", None)
                collection_name = getattr(config, "collection_name", "<unknown>")

                if original_dimension != _expected_dimension:
                    raise RuntimeError(
                        "Unexpected Qdrant vector dimension before "
                        "initialization: "
                        f"collection={collection_name!r}, "
                        f"expected={_expected_dimension}, "
                        f"actual={original_dimension}. "
                        "The MemCube configuration is inconsistent with "
                        "the configured embedder."
                    )

                _original_qdrant_init(self, config)

                # Fail fast if the actual physical collection was not created
                # with the expected embedding dimensionality.
                info = self.client.get_collection(config.collection_name)
                actual_dimension = info.config.params.vectors.size

                if actual_dimension != _expected_dimension:
                    raise RuntimeError(
                        "Qdrant dimension mismatch after initialization: "
                        f"collection={config.collection_name!r}, "
                        f"expected={_expected_dimension}, "
                        f"actual={actual_dimension}"
                    )

                print(
                    "[memos] verified Qdrant dimension:",
                    f"collection={config.collection_name}",
                    f"dimension={actual_dimension}",
                )

            QdrantVecDB.__init__ = _patched_qdrant_init
            QdrantVecDB._mgp6_dimension_patch = True

        modal_url = os.environ.get("MODAL_ENDPOINT_URL")
        if modal_url:
            modal_base_url = f"{modal_url.rstrip('/')}/v1"
            # MemOS reads these env vars at MOS() construction time
            os.environ.setdefault("OPENAI_API_KEY", "dummy")
            os.environ["OPENAI_API_BASE"] = modal_base_url

            import openai

            # Do not hijack the dedicated embedding client.
            # MemOS creates an OpenAI-compatible client for MOS_EMBEDDER_API_BASE;
            # only LLM clients should be redirected to Modal.
            embed_base_url = os.environ.get(
                "MOS_EMBEDDER_API_BASE",
                "http://127.0.0.1:8100/v1",
            ).rstrip("/")

            def _make_modal_init(original_init):
                def _patched(self, *args, **kwargs):
                    requested_base_url = str(kwargs.get("base_url") or "").rstrip("/")

                    # Preserve the local OpenAI-compatible embedding endpoint.
                    if requested_base_url == embed_base_url:
                        return original_init(self, *args, **kwargs)

                    # Redirect only non-embedding OpenAI clients to Modal.
                    kwargs["base_url"] = modal_base_url
                    kwargs["api_key"] = "dummy"
                    hdrs = dict(kwargs.get("default_headers") or {})
                    if os.getenv("MODAL_KEY"):
                        hdrs["Modal-Key"] = os.getenv("MODAL_KEY")
                    if os.getenv("MODAL_SECRET"):
                        hdrs["Modal-Secret"] = os.getenv("MODAL_SECRET")
                    kwargs["default_headers"] = hdrs
                    return original_init(self, *args, **kwargs)

                return _patched

            for _cls in (openai.OpenAI, openai.AsyncOpenAI):
                _cls.__init__ = _make_modal_init(_cls.__init__)

        # Keep the class; construct a physically isolated MOS per scenario.
        # Reusing one MOS._auto_registered_cube across logical cube IDs leaks
        # memory because the underlying MemCube object is shared.
        self._MOS = MOS
        self.mos = None
        self.user_id = "unset"
        self.mem_cube_id = None
        self._scenario_storage_dirs: list[str] = []

    # -- protocol ----------------------------------------------------------
    def reset(self, scenario_id: str) -> None:
        # Hard physical isolation per benchmark scenario.
        scenario_slug = scenario_id.lower()

        storage_dir = tempfile.mkdtemp(prefix=f"mgp6_memos_{scenario_slug}_")
        self._scenario_storage_dirs.append(storage_dir)

        scenario_memos_dir = Path(storage_dir) / ".memos"
        scenario_memos_dir.mkdir(parents=True, exist_ok=True)

        os.environ["MEMOS_BASE_PATH"] = storage_dir

        # MemOS caches MEMOS_DIR at import time. Override the cached value and
        # any modules that imported it directly.
        from memos import settings as memos_settings

        old_memos_dir = getattr(memos_settings, "MEMOS_DIR", None)
        memos_settings.MEMOS_DIR = scenario_memos_dir

        for module in list(sys.modules.values()):
            if module is None:
                continue
            try:
                if getattr(module, "MEMOS_DIR", object()) == old_memos_dir:
                    module.MEMOS_DIR = scenario_memos_dir
            except Exception:
                pass

        self.user_id = f"{scenario_slug}-{uuid.uuid4().hex[:6]}"

        # Build MOS and MemCube explicitly.
        #
        # IMPORTANT:
        # MOS() without a config creates its own auto-configured MemCube using
        # the OpenAI/OpenRouter base URL and the default 3072-dimensional
        # text-embedding-3-large configuration. We intentionally bypass that
        # path here.
        from memos.api.config import APIConfig
        from memos.configs.mem_cube import GeneralMemCubeConfig
        from memos.configs.mem_os import MOSConfig
        from memos.mem_cube.general import GeneralMemCube
        from memos.mem_os.utils.default_config import (
            get_default_config,
            get_default_cube_config,
        )

        llm_api_key = os.environ["OPENAI_API_KEY"]
        llm_api_base = os.environ.get(
            "OPENAI_API_BASE",
            "https://api.openai.com/v1",
        )
        chat_model = os.environ.get(
            "MOS_CHAT_MODEL",
            "gpt-4o-mini",
        )

        embedder_config = APIConfig.get_embedder_config()
        expected_dimension = int(os.environ.get("EMBEDDING_DIMENSION", "384"))

        # ---------------- MOS config ----------------
        mos_config = get_default_config(
            openai_api_key=llm_api_key,
            openai_api_base=llm_api_base,
            text_mem_type="general_text",
            user_id=self.user_id,
            model_name=chat_model,
        )

        # The default helper otherwise gives MemReader the OpenAI/OpenRouter
        # embedder. Replace it with the dedicated local MiniLM configuration.
        mos_config_dict = mos_config.model_dump(mode="python")
        mos_config_dict["mem_reader"]["config"]["embedder"] = embedder_config

        # MemOS schema declares chat_chunker as dict[str, Any] but gives it
        # a default of None. The original model can contain None, but dumping
        # and re-validating it fails under Pydantic strict validation.
        mem_reader_cfg = mos_config_dict["mem_reader"]["config"]
        if mem_reader_cfg.get("chat_chunker") is None:
            mem_reader_cfg["chat_chunker"] = {}

        mos_config = MOSConfig.model_validate(mos_config_dict)

        # Passing an explicit MOSConfig disables MOS auto-cube creation.
        self.mos = self._MOS(mos_config)

        self.mos.create_user(user_id=self.user_id)

        self.mem_cube_id = self.mos.create_cube_for_user(
            cube_name=f"{self.user_id}-cube",
            owner_id=self.user_id,
        )

        # ---------------- MemCube config ----------------
        cube_config = get_default_cube_config(
            openai_api_key=llm_api_key,
            openai_api_base=llm_api_base,
            text_mem_type="general_text",
            user_id=self.user_id,
            model_name=chat_model,
            embedder_model=embedder_config["config"]["model_name_or_path"],
            vector_dimension=expected_dimension,
            cube_id=self.mem_cube_id,
            collection_name=(f"{scenario_slug.replace('-', '_')}_collection"),
        )

        cube_config_dict = cube_config.model_dump(mode="python")

        text_mem_cfg = cube_config_dict["text_mem"]["config"]

        # Explicitly inject the dedicated local embedder into the actual
        # GeneralTextMemory object.
        text_mem_cfg["embedder"] = embedder_config

        # Keep physical vector-store schema exactly aligned with the actual
        # embedding model.
        text_mem_cfg["vector_db"]["config"]["vector_dimension"] = expected_dimension

        cube_config = GeneralMemCubeConfig.model_validate(cube_config_dict)

        scenario_cube = GeneralMemCube(cube_config)

        self.mos.register_mem_cube(
            scenario_cube,
            mem_cube_id=self.mem_cube_id,
            user_id=self.user_id,
        )

        print(
            "[memos] explicit scenario config:",
            f"scenario={scenario_id}",
            f"cube={self.mem_cube_id}",
            f"embedder={embedder_config['config']['model_name_or_path']}",
            f"embed_url={embedder_config['config']['base_url']}",
            f"dimension={expected_dimension}",
            f"storage={scenario_memos_dir}",
        )

    def _cube_call(self, fn, *, write: bool = False, **kwargs):
        """Call a MemOS API while explicitly scoping it to this scenario cube.

        MemOS API names differ slightly between releases, so try the known
        cube-scoping forms in order.
        """
        candidates = [
            {"mem_cube_id": self.mem_cube_id},
            {"writable_cube_ids" if write else "readable_cube_ids": [self.mem_cube_id]},
        ]

        last_type_error = None
        for extra in candidates:
            try:
                return fn(**kwargs, **extra)
            except TypeError as exc:
                msg = str(exc)
                if "unexpected keyword" not in msg:
                    raise
                last_type_error = exc

        raise RuntimeError(
            f"Installed MemOS API exposes no supported cube-scoping argument "
            f"for {getattr(fn, '__name__', fn)!r}"
        ) from last_type_error

    def seed(self, records: list[dict[str, Any]], dialogue: list[dict[str, str]]) -> None:
        for r in records:
            if r.get("status") == "active" and r.get("text"):
                self._cube_call(
                    self.mos.add,
                    write=True,
                    memory_content=r["text"],
                    user_id=self.user_id,
                )

        turns = [
            {"role": m.get("role", "user"), "content": m.get("content", "")}
            for m in dialogue
            if m.get("content")
        ]
        if turns:
            self._cube_call(
                self.mos.add,
                write=True,
                messages=turns,
                user_id=self.user_id,
            )

    def write(self, text: str) -> WriteObservation:
        self._cube_call(
            self.mos.add,
            write=True,
            messages=[{"role": "user", "content": text}],
            user_id=self.user_id,
        )
        # Replacement is not directly observable via the public API.
        return WriteObservation(
            replaced_old=False,
            committed_new=True,
            raw={
                "api": "MOS.add(messages)",
                "mem_cube_id": self.mem_cube_id,
            },
        )

    def snapshot(self) -> list[str]:
        try:
            result = self._cube_call(
                self.mos.get_all,
                user_id=self.user_id,
            )
            return _texts_from(result)
        except Exception:  # noqa: BLE001 - fall back to scoped search
            result = self._cube_call(
                self.mos.search,
                query="user preference fact",
                user_id=self.user_id,
                top_k=20,
            )
            return _texts_from(result)

    def search(self, query: str, k: int = 5) -> list[str]:
        result = self._cube_call(
            self.mos.search,
            query=query,
            user_id=self.user_id,
            top_k=k,
        )
        return _texts_from(result)[:k]

    def meta(self) -> dict[str, Any]:
        return {
            "api": "memos.mem_os.main.MOS (env auto-config)",
            "note": "replaced_old not observable; store-diff mapping only",
        }


if __name__ == "__main__":
    raise SystemExit(run_external(MemOSAdapter))
