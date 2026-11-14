from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Révisions Étudiants — administration"
admin.site.site_title = "Révisions Étudiants"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("compte/", include("accounts.urls")),
    path("cours/", include("courses.urls")),
    path("", include("core.urls")),
]