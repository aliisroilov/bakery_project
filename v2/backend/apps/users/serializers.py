"""User serializers."""
from rest_framework import serializers

from .models import EmployeeGroup, User, UserActivityLog


class CurrentUserSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "role",
            "full_name",
            "display_name",
            "phone",
            "is_superuser",
            "is_archived",
        ]
        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    produced_product_name = serializers.CharField(
        source="produced_product.name", read_only=True, default=""
    )

    class Meta:
        model = User
        fields = [
            "id", "username", "password", "role", "full_name", "display_name",
            "phone", "is_active", "is_archived", "date_joined",
            "produced_product", "produced_product_name",
        ]
        # is_archived is read-only: archiving/restoring must go through the
        # DELETE (archive) and unarchive action so group/shop detachment and
        # restoration run. A bare PATCH must not silently flip it.
        read_only_fields = [
            "date_joined", "display_name", "produced_product_name", "is_archived",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password", None) or User.objects.make_random_password()
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class EmployeeGroupSerializer(serializers.ModelSerializer):
    member_ids = serializers.PrimaryKeyRelatedField(
        source="members",
        many=True,
        queryset=User.objects.filter(role="nonvoy"),
        required=False,
    )
    members_display = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeGroup
        fields = ["id", "name", "member_ids", "members_display", "note", "created_at"]
        read_only_fields = ["created_at"]

    def get_members_display(self, obj):
        return [{"id": u.id, "display_name": u.display_name} for u in obj.members.all()]

    def create(self, validated_data):
        members = validated_data.pop("members", [])
        group = EmployeeGroup.objects.create(**validated_data)
        group.members.set(members)
        return group

    def update(self, instance, validated_data):
        members = validated_data.pop("members", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        if members is not None:
            instance.members.set(members)
        return instance


def describe_action(method: str, path: str) -> str:
    """Map (HTTP method, URL path) → human-readable Uzbek action label."""
    m = (method or "").upper()
    p = path or ""

    # Exact/suffix matches first
    if "/orders/" in p and "/confirm_delivery/" in p and m == "POST":
        return "Yetkazib berish tasdiqlandi"
    if "/orders/" in p and "/repeat/" in p and m == "POST":
        return "Buyurtma takrorlandi"
    if "/products/recalc-costs/" in p and m == "POST":
        return "Tan narx qayta hisoblandi"
    if "/inventory/purchases/" in p and m == "POST":
        return "Xomashyo xaridi qo'shildi"
    if "/inventory/recipes/" in p and m == "POST":
        return "Retsept qo'shildi"
    if "/inventory/ingredients/" in p and "/adjust/" in p and m == "POST":
        return "Xomashyo zaxirasi to'g'irlandi"
    if "/production/" in p and m == "POST":
        return "Ishlab chiqarish yozuvi qo'shildi"
    if "/finance/payments/" in p and m == "POST":
        return "To'lov qayd qilindi"
    if "/salary/pay/" in p and m == "POST":
        return "Oylik to'landi"
    if "/shops/" in p and "/prices/" in p:
        if m == "POST":
            return "Do'kon narxi saqlandi"
        if m == "DELETE":
            return "Do'kon narxi o'chirildi"
    if "/auth/login" in p and m == "POST":
        return "Tizimga kirdi"
    if "/auth/logout" in p and m == "POST":
        return "Tizimdan chiqdi"

    # Generic CRUD by resource
    resource_labels = [
        ("/orders/", "Buyurtma"),
        ("/shops/", "Do'kon"),
        ("/products/", "Mahsulot"),
        ("/inventory/ingredients/", "Xomashyo"),
        ("/users/", "Xodim"),
        ("/regions/", "Hudud"),
        ("/finance/accounts/", "Kassa"),
    ]
    for key, label in resource_labels:
        if key in p:
            if m == "POST":
                return f"{label} yaratildi"
            if m in ("PATCH", "PUT"):
                return f"{label} tahrirlandi"
            if m == "DELETE":
                return f"{label} arxivlandi"
            if m == "GET":
                return f"{label} ko'rildi"

    if m == "GET":
        return "Ko'rib chiqildi"
    if m == "POST":
        return "Qo'shildi"
    if m in ("PATCH", "PUT"):
        return "O'zgartirildi"
    if m == "DELETE":
        return "O'chirildi"
    return m or "—"


class UserActivityLogSerializer(serializers.ModelSerializer):
    user_display = serializers.CharField(source="user.display_name", read_only=True)
    action = serializers.SerializerMethodField()

    class Meta:
        model = UserActivityLog
        fields = [
            "id", "user", "user_display",
            "path", "method", "status_code", "ip", "timestamp",
            "action",
        ]

    def get_action(self, obj) -> str:
        return describe_action(obj.method, obj.path)
