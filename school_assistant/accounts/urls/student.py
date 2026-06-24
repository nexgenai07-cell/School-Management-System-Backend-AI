from django.urls import path, include
from rest_framework.routers import DefaultRouter
from accounts.views.student import StudentViewSet

router = DefaultRouter()
router.register(r'students', StudentViewSet, basename="students")

urlpatterns = [
    path("", include(router.urls)),
]
