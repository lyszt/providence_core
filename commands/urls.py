from django.urls import path
from . import views

app_name = "commands"

urlpatterns = [
    path("dispatch/", views.dispatch, name="dispatch"),
    path("math/", views.math, name="math"),
    path("college/", views.college, name="college"),
]
