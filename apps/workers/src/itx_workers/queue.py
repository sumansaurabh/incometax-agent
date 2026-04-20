from dataclasses import dataclass


@dataclass
class QueueJob:
    document_id: str
    doc_type: str


def enqueue(job: QueueJob) -> QueueJob:
    return job
