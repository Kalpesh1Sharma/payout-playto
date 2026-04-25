from .models import AuditLog


def log_audit(
    *,
    merchant,
    action,
    resource_type,
    resource_id,
    metadata=None,
    actor_type="SYSTEM",
    actor_id=None,
):
    AuditLog.objects.create(
        merchant=merchant,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        metadata=metadata or {},
    )
