from django.contrib import admin

from .models import ClassSlot, Exam


@admin.register(ClassSlot)
class ClassSlotAdmin(admin.ModelAdmin):
    list_display = ("__str__", "owner")
    list_filter = ("weekday",)


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ("__str__", "owner", "date")
    list_filter = ("date",)