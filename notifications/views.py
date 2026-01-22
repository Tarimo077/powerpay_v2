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
    # Only get unread notifications
    notifications = request.user.notifications.filter(is_read=False).order_by('-created_at')[:5]
    unread_exists = notifications.exists()
    
    html = render_to_string(
        'notifications/dropdown.html',
        {'notifications': notifications, 'unread_exists': unread_exists}
    )
    return HttpResponse(html)

@login_required
def unread_count(request):
    count = request.user.notifications.filter(is_read=False).count()
    if count == 0:
        return HttpResponse('')  # hide badge
    html = f'''
    <span id="notifCount"
          class="badge badge-md bg-orange-500 text-white text-lg font-semibold text-center absolute -top-2 left-5 rounded-full w-6 h-6">
        {count}
    </span>
    '''
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