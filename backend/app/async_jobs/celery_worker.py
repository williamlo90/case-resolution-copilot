from app.async_jobs.celery_app import create_celery_app

app = create_celery_app()

__all__ = ["app"]
