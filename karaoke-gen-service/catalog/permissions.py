from rest_framework import permissions


class IsSongOwnerOrAdminOrReadOnly(permissions.BasePermission):
    """Allow reads for visible songs and writes only for owners or admins."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user.is_staff or obj.uploaded_by_id == request.user.id
