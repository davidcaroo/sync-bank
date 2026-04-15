from __future__ import annotations


def enqueue_causar_factura(*, job_id: str, factura_id: str, overrides_map: dict | None = None) -> None:
    from workers.tasks import causar_factura_job

    causar_factura_job.send(job_id=job_id, factura_id=factura_id, overrides_map=overrides_map or {})
