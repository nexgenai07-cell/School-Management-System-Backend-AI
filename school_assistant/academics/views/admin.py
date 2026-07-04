"""
ACADEMICS -- ADMIN-ROLE VIEWS
================================
"""

from rest_framework import viewsets

from academics.models import ClassSection, Subject, Room, Timetable
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from accounts.permissions import IsAdmin
from academics.serializers.admin import (
    ClassSectionSerializer, SubjectSerializer, RoomSerializer, TimetableSerializer,
)


class ClassSectionViewSet(viewsets.ModelViewSet):
    """CRUD /api/admin/classes"""
    queryset = ClassSection.objects.all()
    serializer_class = ClassSectionSerializer
    permission_classes = [IsAdmin]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['class_name', 'section']
    search_fields = ['class_name', 'section']
    ordering_fields = ['class_name', 'section', 'created_at']
    ordering = ['class_name', 'section']


class SubjectViewSet(viewsets.ModelViewSet):
    """CRUD /api/admin/subjects"""
    queryset = Subject.objects.select_related("class_section", "assigned_teacher").all()
    serializer_class = SubjectSerializer
    permission_classes = [IsAdmin]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['class_section', 'assigned_teacher']
    search_fields = ['subject_name']
    ordering_fields = ['subject_name', 'class_section']
    ordering = ['subject_name']


class RoomViewSet(viewsets.ModelViewSet):
    """CRUD /api/admin/rooms"""
    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    permission_classes = [IsAdmin]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['capacity']
    search_fields = ['name', 'location']
    ordering_fields = ['name', 'capacity']
    ordering = ['name']

class TimetableViewSet(viewsets.ModelViewSet):
    """CRUD /api/admin/timetable"""
    queryset = Timetable.objects.select_related("class_section", "subject", "teacher", "room").all()
    serializer_class = TimetableSerializer
    permission_classes = [IsAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['class_section', 'teacher', 'room', 'day']
    search_fields = ['subject__subject_name']
    ordering_fields = ['day', 'start_time', 'end_time']
    ordering = ['day', 'start_time']