from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Révisions Étudiants — administration"
admin.site.site_title = "Révisions Étudiants"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("compte/", include("accounts.urls")),
    path("cours/", include("courses.urls")),
    path("quiz/", include("quizzes.urls")),
    path("revisions/", include("reviews.urls")),
    path("", include("core.urls")),
]

# En développement uniquement : Django sert les fichiers envoyés (dossier media/).
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)