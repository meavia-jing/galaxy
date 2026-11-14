from django.urls import path

from .views import BannerListView, ContentPageDetailView

urlpatterns = [
    path("banners/", BannerListView.as_view(), name="banner-list"),
    path("pages/<slug:slug>/", ContentPageDetailView.as_view(), name="content-page"),
]
