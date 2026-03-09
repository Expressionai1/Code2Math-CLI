import json
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


class ResultSaver:
    def __init__(self, output_path: str | Path, problem_ids: set[int]):
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.problem_ids = problem_ids
        self._lock = threading.Lock()
        # 使用 dict 存储结果，键为 problem_id
        self._results: dict[int, dict] = {}

        # 加载已有结果
        if self.output_path.exists():
            with open(self.output_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            for entry in existing:
                if "problem_id" in entry and entry["problem_id"] in problem_ids:
                    self._results[entry["problem_id"]] = entry

    def save_result(self, problem_id: int, result: dict) -> None:
        with self._lock:
            # 添加 problem_id 到结果中
            result["problem_id"] = problem_id
            self._results[problem_id] = result
            self._flush()

    def _flush(self) -> None:
        # 按 problem_id 排序输出
        output = [
            self._results[pid]
            for pid in sorted(self.problem_ids)
            if pid in self._results
        ]
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

    @staticmethod
    def make_output_filename(model_id: str, run: int = 1, demo_count: int = 6) -> str:
        return f"{model_id}_{model_id}_{run}_with_demo_{demo_count}.json"
