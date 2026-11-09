from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Datasource
from .serializers import DatasourceSerializer
from accounts.permissions import IsOwnerOrAdmin
from jobs.models import Job


def _scope(qs, user):
    qs = qs.filter(tenant=user.tenant)
    if user.role != "admin":
        qs = qs.filter(owner=user)
    return qs


class DatasourceListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = _scope(Datasource.objects.all(), request.user).order_by("-created_at")
        return Response(DatasourceSerializer(qs, many=True).data)

    def post(self, request):
        ser = DatasourceSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        ds = ser.save()
        return Response(DatasourceSerializer(ds).data, status=status.HTTP_201_CREATED)


class DatasourceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, pk):
        try:
            ds = _scope(Datasource.objects.all(), request.user).get(pk=pk)
            return ds
        except Datasource.DoesNotExist:
            return None

    def get(self, request, pk):
        ds = self.get_object(request, pk)
        if not ds:
            return Response({"detail": "Not found"}, status=404)
        return Response(DatasourceSerializer(ds).data)

    def patch(self, request, pk):
        ds = self.get_object(request, pk)
        if not ds:
            return Response({"detail": "Not found"}, status=404)
        ser = DatasourceSerializer(ds, data=request.data, partial=True, context={"request": request})
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(DatasourceSerializer(ds).data)

    def delete(self, request, pk):
        ds = self.get_object(request, pk)
        if not ds:
            return Response({"detail": "Not found"}, status=404)
        if Job.objects.filter(datasource=ds, status__in=["queued", "running"]).exists():
            return Response({"detail": "Cannot delete: running job references this datasource"}, status=400)
        ds.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
