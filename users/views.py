from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.contrib.auth.views import LoginView


def user_login(request):
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('dashboard')
        else:
            return render(request, 'users/login.html', {'error': 'Username yoki parol xato'})
    return render(request, 'users/login.html')

@login_required
def user_logout(request):
    logout(request)
    return redirect('login')



from django.contrib.auth.views import LoginView

class CustomLoginView(LoginView):
    template_name = "users/login.html"

    def get_success_url(self):
        user = self.request.user
        if user.role == "viewer":
            return "/dashboard/admins/"
        elif user.role == "manager":
            return "/dashboard/"
        elif user.role == "driver":
            return "/dashboard/"
        return "/"
