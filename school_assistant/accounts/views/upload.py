from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status

import cloudinary.uploader

from accounts.serializers.upload_serializer import FileUploadSerializer


class FileUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        operation_summary="Upload a file (multipart/form-data)",
        consumes=["multipart/form-data"],
        manual_parameters=[
            openapi.Parameter(
                name="file",
                in_=openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=True,
                description="File to upload",
            )
        ],
        responses={
            201: openapi.Response(
                description="Upload successful",
                examples={"application/json": {"url": "https://..."}},
            ),
            400: "Bad request",
        },
    )
    def post(self, request):
        serializer = FileUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file_obj = serializer.validated_data["file"]
        result = cloudinary.uploader.upload(file_obj, resource_type="auto")
        return Response({"url": result["secure_url"]}, status=status.HTTP_201_CREATED)


