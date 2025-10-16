from django.urls import path
from . import views

app_name = "salary"

urlpatterns = [
    path("", views.employee_list, name="employee_list"),
    path("pay/<int:user_id>/", views.pay_salary, name="pay_salary"),
    path("history/<int:user_id>/", views.salary_history, name="salary_history"),
]
