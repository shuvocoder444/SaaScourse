import os
import sys
import django

sys.stdout.reconfigure(encoding='utf-8')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saascourse.settings')
django.setup()

from django.test import Client
from apps.tenants.models import Tenant
from apps.users.models import User
from apps.courses.models import (
    FeedPost, FeedLike, FeedComment,
    ClassRoutine, StudentResult,
    SupportThread, SupportChatMessage,
    StudentInvoice, BookOrder,
    StudentClub, Book, Course
)

def run_tests():
    tenant = Tenant.objects.filter(slug='alpha').first()
    student = User.objects.get(email='alex@student.com')

    client = Client(HTTP_HOST='alpha.localhost:8001')
    client.force_login(student)

    print("=== Testing Student Dashboard Navigation & Rendering ===")
    tabs = [
        ('newsfeed', 'নিউজ ফিড'),
        ('my_courses', 'আমার কোর্সসমূহ'),
        ('routine', 'ক্লাস রুটিন'),
        ('results', 'ফলাফল'),
        ('support', 'সাপোর্ট'),
        ('profile', 'প্রোফাইল'),
        ('invoices', 'ইনভয়েস'),
        ('orders', 'আমার অর্ডার'),
        ('clubs', 'ক্লাব'),
        ('browse_courses', 'সকল কোর্স'),
        ('browse_books', 'সকল বই'),
    ]

    for tab_name, label in tabs:
        res = client.get(f'/dashboard/?tab={tab_name}')
        assert res.status_code == 200, f"Tab {tab_name} failed with status {res.status_code}"
        print(f" [PASS] Tab: {tab_name} ({label}) rendered successfully (HTTP 200)")

    print("\n=== Testing Student Dashboard Actions (POST) ===")

    # 1. Create feed post
    res = client.post('/dashboard/', {
        'action': 'create_feed_post',
        'title': 'টেস্ট পোস্ট - স্টুডেন্ট কমিউনিটি',
        'content': 'আজকের ক্লাসের নোটগুলো খুবই স্পষ্ট ছিল। সবাইকে ধন্যবাদ!',
        'category': 'general'
    }, follow=True)
    assert res.status_code == 200
    created_post = FeedPost.objects.filter(author=student, title='টেস্ট পোস্ট - স্টুডেন্ট কমিউনিটি').first()
    assert created_post is not None, "Feed post creation failed!"
    print(f" [PASS] Action: create_feed_post succeeded (ID: {created_post.id})")

    # 2. Like feed post
    res = client.post('/dashboard/', {
        'action': 'like_feed_post',
        'post_id': created_post.id
    }, follow=True)
    assert res.status_code == 200
    assert FeedLike.objects.filter(post=created_post, user=student).exists(), "Feed like failed!"
    print(" [PASS] Action: like_feed_post succeeded")

    # 3. Comment feed post
    res = client.post('/dashboard/', {
        'action': 'comment_feed_post',
        'post_id': created_post.id,
        'content': 'আমারও একই মতামত!'
    }, follow=True)
    assert res.status_code == 200
    assert FeedComment.objects.filter(post=created_post, author=student, content='আমারও একই মতামত!').exists()
    print(" [PASS] Action: comment_feed_post succeeded")

    # 4. Support message
    thread = SupportThread.objects.filter(student=student, tenant=tenant).first()
    res = client.post('/dashboard/', {
        'action': 'send_support_message',
        'thread_id': thread.id,
        'message': 'ধন্যবাদ স্যার, এখন ঠিকমতো কাজ করছে।'
    }, follow=True)
    assert res.status_code == 200
    assert SupportChatMessage.objects.filter(thread=thread, sender=student, message='ধন্যবাদ স্যার, এখন ঠিকমতো কাজ করছে।').exists()
    print(" [PASS] Action: send_support_message succeeded")

    # 5. Club Post
    club = StudentClub.objects.filter(tenant=tenant).first()
    res = client.post('/dashboard/', {
        'action': 'create_club_post',
        'club_id': club.id,
        'title': 'ক্লাব আলোচনা পোস্ট',
        'content': 'এই সপ্তাহের লাইভ সেশনে কারা কারা জয়েন করছ?'
    }, follow=True)
    assert res.status_code == 200
    print(" [PASS] Action: create_club_post succeeded")

    # 6. Book Order
    book = Book.objects.filter(tenant=tenant).first()
    if book:
        res = client.post('/dashboard/', {
            'action': 'order_book',
            'book_id': book.id,
            'quantity': 2,
            'shipping_name': 'Alex Hasan',
            'phone_number': '01899887766',
            'shipping_address': 'বাড়ি ২০, রোড ৫, মিরপুর ১০, ঢাকা'
        }, follow=True)
        assert res.status_code == 200
        order = BookOrder.objects.filter(student=student, phone_number='01899887766').first()
        assert order is not None, "Book order failed!"
        print(f" [PASS] Action: order_book succeeded (Order #{order.id}, Qty: {order.quantity})")

    print("\n ALL STUDENT DASHBOARD TESTS PASSED!")

if __name__ == '__main__':
    run_tests()
