from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.models import db, Ticket, TicketMessage, User, LeagueMatch
from app.utils import get_current_time
from app.firebase_utils import send_push_notification

tickets = Blueprint('tickets', __name__)

def notify_admins(title, body, url=None):
    admins = User.query.filter((User.is_admin == True) | (User.is_mod == True)).all()
    for admin in admins:
        if admin.fcm_token:
            send_push_notification(admin.fcm_token, title, body, data={'url': url} if url else None)

def notify_user(user, title, body, url=None):
    if user.fcm_token:
        send_push_notification(user.fcm_token, title, body, data={'url': url} if url else None)

@tickets.route('/tickets')
@login_required
def list_tickets():
    # User sees only their tickets. Admins see all.
    # Optionally, admins can filter.
    if current_user.is_admin or current_user.is_mod:
        # Show all open tickets first, then resolved/closed
        tickets_query = Ticket.query.order_by(
            Ticket.status == 'closed', # False (0) first, True (1) last
            Ticket.updated_at.desc()
        ).all()
    else:
        tickets_query = Ticket.query.filter_by(author_id=current_user.id).order_by(Ticket.updated_at.desc()).all()
        
    return render_template('tickets/list.html', tickets=tickets_query)

@tickets.route('/tickets/new', methods=['GET', 'POST'])
@login_required
def create_ticket():
    if request.method == 'POST':
        title = request.form.get('title')
        category = request.form.get('category')
        description = request.form.get('description')
        
        if not title or not description:
            flash("Bitte Titel und Beschreibung ausfüllen.", "error")
            return redirect(url_for('tickets.create_ticket'))
            
        ticket = Ticket(
            title=title,
            category=category,
            description=description,
            author_id=current_user.id
        )
        db.session.add(ticket)
        db.session.commit()
        
        # Notify Admins
        notify_admins(
            f"Neues Ticket: {title}",
            f"Von {current_user.username} ({category})",
            url=url_for('tickets.detail', ticket_id=ticket.id, _external=True)
        )
        
        flash("Ticket erfolgreich erstellt.", "success")
        return redirect(url_for('tickets.detail', ticket_id=ticket.id))
        
    return render_template('tickets/create.html')

@tickets.route('/tickets/<int:ticket_id>', methods=['GET'])
@login_required
def detail(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    
    # Permission check
    if not (current_user.is_admin or current_user.is_mod or ticket.author_id == current_user.id):
        flash("Keine Berechtigung für dieses Ticket.", "error")
        return redirect(url_for('tickets.list_tickets'))
        
    return render_template('tickets/detail.html', ticket=ticket)

@tickets.route('/tickets/<int:ticket_id>/reply', methods=['POST'])
@login_required
def reply(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    
    # Permission check
    if not (current_user.is_admin or current_user.is_mod or ticket.author_id == current_user.id):
        abort(403)
        
    content = request.form.get('content')
    if content:
        msg = TicketMessage(
            ticket_id=ticket.id,
            author_id=current_user.id,
            content=content
        )
        db.session.add(msg)
        
        # Update timestamp
        ticket.updated_at = get_current_time()
        
        # Notifications
        if current_user.is_admin or current_user.is_mod:
            # Reply from Staff -> Notify Author
            if ticket.author_id != current_user.id:
                notify_user(
                    ticket.author,
                    f"Antwort im Ticket #{ticket.id}",
                    f"Von {current_user.username}: {content[:50]}...",
                    url=url_for('tickets.detail', ticket_id=ticket.id, _external=True)
                )
        else:
            # Reply from User -> Notify Admins
            notify_admins(
                f"Antwort in Ticket #{ticket.id}",
                f"Von {current_user.username}: {content[:50]}...",
                url=url_for('tickets.detail', ticket_id=ticket.id, _external=True)
            )
        
        db.session.commit()
        flash("Nachricht gesendet.", "success")
        
    return redirect(url_for('tickets.detail', ticket_id=ticket_id))

@tickets.route('/tickets/<int:ticket_id>/status', methods=['POST'])
@login_required
def change_status(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    
    # Only Admin/Mod or the Author (to close) can change status
    if not (current_user.is_admin or current_user.is_mod or ticket.author_id == current_user.id):
        abort(403)
        
    new_status = request.form.get('status')
    if new_status in ['open', 'in_progress', 'resolved', 'closed']:
        old_status = ticket.status
        ticket.status = new_status
        ticket.updated_at = get_current_time()
        
        # Notify User if status changed by Admin
        if (current_user.is_admin or current_user.is_mod) and ticket.author_id != current_user.id:
             notify_user(
                ticket.author,
                f"Ticket #{ticket.id} Status Update",
                f"Status wurde geändert auf: {new_status}",
                url=url_for('tickets.detail', ticket_id=ticket.id, _external=True)
            )
        
        db.session.commit()
        flash(f"Status geändert auf: {new_status}", "success")
        
    return redirect(url_for('tickets.detail', ticket_id=ticket_id))
