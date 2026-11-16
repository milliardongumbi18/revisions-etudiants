from django.contrib import admin

from .models import ReviewCard, ReviewLog


@admin.register(ReviewCard)
class ReviewCardAdmin(admin.ModelAdmin):
    list_display = ("question", "owner", "due_date", "interval", "easiness", "repetitions")
    list_filter = ("due_date",)
    search_fields = ("question__text", "owner__username")


@admin.register(ReviewLog)
class ReviewLogAdmin(admin.ModelAdmin):
    list_display = ("card", "owner", "grade", "correct", "reviewed_at")
    list_filter = ("correct",)