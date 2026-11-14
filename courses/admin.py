from django.contrib import admin

from .models import Chapter, Course


class ChapterInline(admin.TabularInline):
    model = Chapter
    extra = 0
    fields = ("order", "title")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "color", "updated_at")
    list_filter = ("color",)
    search_fields = ("title", "owner__username")
    inlines = [ChapterInline]