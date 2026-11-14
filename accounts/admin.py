from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin des utilisateurs : celui de Django + nos champs."""

    list_display = ("username", "email", "university", "program", "is_staff")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Études", {"fields": ("university", "program")}),
    )
    # Formulaire de création : on ajoute l'e-mail, qui est obligatoire chez nous.
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Contact", {"fields": ("email",)}),
    )