"""I02-T04 acceptance tests: address CRUD, isolation and default-address rules."""
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Address, User

VALID = {
    "recipient": "张三",
    "phone": "13800138000",
    "province": "广东省",
    "city": "深圳市",
    "district": "南山区",
    "detail": "科技园路 1 号 101 室",
}


def payload(**overrides):
    data = dict(VALID)
    data.update(overrides)
    return data


class AddressApiTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice001", "AlicePass2026!")
        self.bob = User.objects.create_user("bob00001", "BobPass2026!")
        self.client = APIClient()
        self.client.force_authenticate(self.alice)

    def create(self, **overrides):
        response = self.client.post("/api/v1/addresses/", payload(**overrides), format="json")
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()["data"]

    def test_requires_authentication(self):
        anonymous = APIClient()
        self.assertEqual(anonymous.get("/api/v1/addresses/").status_code, 401)
        self.assertEqual(
            anonymous.post("/api/v1/addresses/", payload(), format="json").status_code, 401
        )

    def test_first_address_is_default(self):
        data = self.create()
        self.assertTrue(data["is_default"])
        self.assertEqual(data["recipient"], "张三")
        self.assertIsInstance(data["id"], str)

    def test_switching_default_keeps_exactly_one(self):
        first = self.create()
        second = self.create(recipient="李四", is_default=True)
        self.assertTrue(second["is_default"])
        self.assertFalse(Address.objects.get(pk=first["id"]).is_default)
        self.assertEqual(Address.objects.filter(user=self.alice, is_default=True).count(), 1)

    def test_update_can_promote_default(self):
        first = self.create()
        self.create(recipient="李四")
        response = self.client.patch(
            f"/api/v1/addresses/{first['id']}/", {"is_default": True}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Address.objects.filter(user=self.alice, is_default=True).count(), 1)

    def test_cannot_clear_the_only_default(self):
        only = self.create()
        response = self.client.patch(
            f"/api/v1/addresses/{only['id']}/", {"is_default": False}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(Address.objects.get(pk=only["id"]).is_default)

    def test_other_users_address_is_invisible(self):
        bob_address = Address.objects.create(user=self.bob, **payload())
        self.assertNotIn(
            str(bob_address.pk),
            [item["id"] for item in self.client.get("/api/v1/addresses/").json()["data"]],
        )
        for method in (self.client.get, self.client.delete):
            response = method(f"/api/v1/addresses/{bob_address.pk}/")
            self.assertEqual(response.status_code, 404, method.__name__)
        patch = self.client.patch(
            f"/api/v1/addresses/{bob_address.pk}/", {"recipient": "黑客"}, format="json"
        )
        self.assertEqual(patch.status_code, 404)
        bob_address.refresh_from_db()
        self.assertEqual(bob_address.recipient, "张三")

    def test_cannot_assign_address_to_another_user(self):
        response = self.client.post(
            "/api/v1/addresses/", payload(user=str(self.bob.pk)), format="json"
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Address.objects.get(user=self.alice).recipient, "张三")
        self.assertFalse(Address.objects.filter(user=self.bob).exists())

    def test_delete_default_promotes_another(self):
        first = self.create()
        second = self.create(recipient="李四")
        response = self.client.delete(f"/api/v1/addresses/{first['id']}/")
        self.assertEqual(response.status_code, 204)
        self.assertTrue(Address.objects.get(pk=second["id"]).is_default)
        self.assertEqual(Address.objects.filter(user=self.alice, is_default=True).count(), 1)

    def test_delete_last_address_leaves_none(self):
        only = self.create()
        self.assertEqual(self.client.delete(f"/api/v1/addresses/{only['id']}/").status_code, 204)
        self.assertFalse(Address.objects.filter(user=self.alice).exists())

    def test_invalid_phone_rejected(self):
        response = self.client.post(
            "/api/v1/addresses/", payload(phone="12345"), format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("phone", response.json()["error"]["fields"])

    def test_blank_fields_rejected(self):
        response = self.client.post(
            "/api/v1/addresses/", payload(detail="   "), format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.json()["error"]["fields"])

    def test_trims_whitespace_and_stores_plain_text(self):
        data = self.create(recipient="  王五  ", detail="  花园街 8 号  ")
        self.assertEqual(data["recipient"], "王五")
        self.assertEqual(data["detail"], "花园街 8 号")

    def test_address_limit(self):
        for index in range(20):
            Address.objects.create(user=self.alice, **payload(recipient=f"用户{index}"))
        response = self.client.post("/api/v1/addresses/", payload(), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "ADDRESS_LIMIT")
        self.assertEqual(Address.objects.filter(user=self.alice).count(), 20)
