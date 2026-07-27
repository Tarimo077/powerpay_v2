from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.core.paginator import Paginator


@login_required
def notification_list(request):
    notifications_qs = request.user.notifications.all().order_by('-created_at')
    unread_exists = notifications_qs.filter(is_read=False).exists()

    per_page = int(request.GET.get('per_page', 5))  # default 10 per page
    page_number = request.GET.get('page', 1)
    paginator = Paginator(notifications_qs, per_page)
    notifications_page = paginator.get_page(page_number)

    context = {
        'notifications': notifications_page,  # Page object
        'per_page': per_page,
        'unread_exists': unread_exists,
    }
    return render(request, 'notifications/list.html', context)

@login_required
def mark_all_as_read_list(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return redirect('notifications:list')

@login_required
def mark_all_as_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return HttpResponse('')

@login_required
def dropdown(request):
    notifications = list(request.user.notifications.filter(is_read=False).order_by('-created_at')[:5])
    html = render_to_string(
        'notifications/dropdown.html',
        {'notifications': notifications, 'unread_exists': len(notifications) > 0},
        request=request,
    )
    return HttpResponse(html)

@login_required
def unread_count(request):
    count = request.user.notifications.filter(is_read=False).count()
    if count == 0:
        return HttpResponse('')
    html = f'''<span class="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 text-[9px] font-bold text-white px-1">{count}</span>'''
    return HttpResponse(html)

@login_required
def mark_read(request, notif_id):
    notif = get_object_or_404(request.user.notifications, id=notif_id)
    notif.is_read = True
    notif.save()
    return HttpResponse('')  

@login_required
def mark_read_list(request, notif_id):
    notif = get_object_or_404(request.user.notifications, id=notif_id)
    notif.is_read = True
    notif.save()

    html = render_to_string('notifications/single_notification.html', {
        'notification': notif
    })

    return HttpResponse(html)