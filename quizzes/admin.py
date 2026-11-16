from django.contrib import admin

from .models import Question, Quiz


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 0


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("__str__", "generated_by", "created_at")
    search_fields = ("chapter__title", "chapter__course__owner__username")
    inlines = [QuestionInline]