from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.email_service import check_emails

scheduler = AsyncIOScheduler()

def start_scheduler():
    scheduler.add_job(check_emails, 'interval', minutes=5)
    scheduler.start()
