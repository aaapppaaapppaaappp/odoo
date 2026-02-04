from datetime import timedelta

from babel.dates import format_date as babel_format_date

from odoo import _, http
from odoo.exceptions import ValidationError
from odoo.http import Controller, request


class DispatchPortal(Controller):

    def _get_employee_from_token(self, access_token):
        if not access_token:
            return None
        employee = request.env['hr.employee'].sudo().search([
            ('access_token', '=', access_token),
            ('active', '=', True),
        ], limit=1)
        return employee or None

    @staticmethod
    def _get_shift_labels():
        return dict(
            request.env['dispatch.shift.template']
            ._fields['shift_label']
            ._description_selection(request.env)
        )

    @staticmethod
    def _format_hour(h):
        return '%d:%02d' % (int(h), int(h % 1 * 60))

    @staticmethod
    def _format_weekday(d):
        lang = request.env.lang or 'en_US'
        try:
            return babel_format_date(d, format='EEE', locale=lang)
        except Exception:
            return d.strftime('%a')

    @http.route('/dispatch/my', type='http', auth='public', website=True)
    def dispatch_home(self, access_token=None, **kw):
        employee = self._get_employee_from_token(access_token)
        if not employee:
            return request.render('dispatch_shift.portal_invalid_token')

        # Flash message: read once then clear
        message = request.session.pop('dispatch_message', None)

        applications = request.env['dispatch.shift.application'].sudo().search([
            ('employee_id', '=', employee.id),
            ('state', 'in', ('applied', 'confirmed', 'waitlisted', 'rejected')),
        ], order='slot_date asc')

        campaigns = request.env['dispatch.campaign'].sudo().search([
            ('state', '=', 'open'),
            '|',
            ('invite_only', '=', False),
            ('invited_employee_ids', 'in', [employee.id]),
        ])

        labels = {
            'welcome': _('Welcome,'),
            'available_campaigns': _('Available Campaigns'),
            'browse_shifts': _('Browse Shifts'),
            'blocked': _('Blocked'),
            'no_campaigns': _('No campaigns are currently open.'),
            'my_shifts': _('My Shifts'),
            'date': _('Date'),
            'store': _('Store'),
            'shift': _('Shift'),
            'time': _('Time'),
            'status': _('Status'),
            'applied': _('Applied'),
            'confirmed': _('Confirmed'),
            'waitlisted': _('Waitlisted'),
            'rejected': _('Rejected'),
            'cancel': _('Cancel'),
            'cancel_confirm': _('Cancel this shift?'),
            'no_shifts': _('You have no shifts yet. Browse a campaign above to apply!'),
        }

        return request.render('dispatch_shift.portal_home', {
            'employee': employee,
            'applications': applications,
            'campaigns': campaigns,
            'access_token': access_token,
            'message': message,
            'shift_labels': self._get_shift_labels(),
            'format_hour': self._format_hour,
            'labels': labels,
        })

    @http.route('/dispatch/campaign/<int:campaign_id>/browse',
                type='http', auth='public', website=True)
    def dispatch_browse(self, campaign_id, access_token=None, **kw):
        employee = self._get_employee_from_token(access_token)
        if not employee:
            return request.render('dispatch_shift.portal_invalid_token')

        campaign = request.env['dispatch.campaign'].sudo().browse(campaign_id)
        if not campaign.exists() or campaign.state != 'open':
            return request.redirect('/dispatch/my?access_token=%s' % access_token)

        if campaign.invite_only and employee not in campaign.invited_employee_ids:
            return request.redirect('/dispatch/my?access_token=%s' % access_token)

        # Flash error: read once then clear
        error = request.session.pop('dispatch_error', None)

        is_frozen = employee in campaign.frozen_employee_ids

        slots = request.env['dispatch.shift.slot'].sudo().search([
            ('campaign_id', '=', campaign.id),
        ], order='date, template_id')

        # Build the grid structure
        templates = campaign.template_ids.sorted(lambda t: (t.store_id.name or '', t.start_hour))

        # Get existing applications for this employee in this campaign
        existing_apps = request.env['dispatch.shift.application'].sudo().search([
            ('employee_id', '=', employee.id),
            ('slot_id.campaign_id', '=', campaign.id),
            ('state', 'in', ('applied', 'confirmed', 'waitlisted')),
        ])
        applied_slot_ids = set(existing_apps.mapped('slot_id').ids)

        # Get rejected applications to block reapplication
        rejected_apps = request.env['dispatch.shift.application'].sudo().search([
            ('employee_id', '=', employee.id),
            ('slot_id.campaign_id', '=', campaign.id),
            ('state', '=', 'rejected'),
        ])
        rejected_slot_ids = set(rejected_apps.mapped('slot_id').ids)

        # Build date list
        dates = []
        current = campaign.date_start
        while current <= campaign.date_end:
            dates.append(current)
            current += timedelta(days=1)

        # Build slot lookup: (template_id, date) -> slot
        slot_map = {}
        for slot in slots:
            slot_map[(slot.template_id.id, slot.date)] = slot

        labels = {
            'client': _('Client:'),
            'max_consecutive_days': _('Max consecutive days:'),
            'back': _('Back'),
            'you_are_blocked': _('You are blocked'),
            'blocked_message': _('from applying to shifts in this campaign. Please contact your dispatch coordinator if you believe this is an error.'),
            'date': _('Date'),
            'applied': _('Applied'),
            'rejected': _('Rejected'),
            'full': _('Full'),
            'waitlist': _('waitlist'),
            'apply_for_selected': _('Apply for Selected Shifts'),
            'applications_blocked': _('Applications Blocked'),
        }

        return request.render('dispatch_shift.portal_browse', {
            'employee': employee,
            'campaign': campaign,
            'templates': templates,
            'dates': dates,
            'slot_map': slot_map,
            'applied_slot_ids': applied_slot_ids,
            'rejected_slot_ids': rejected_slot_ids,
            'access_token': access_token,
            'error': error,
            'is_frozen': is_frozen,
            'shift_labels': self._get_shift_labels(),
            'format_hour': self._format_hour,
            'format_weekday': self._format_weekday,
            'labels': labels,
        })

    @http.route('/dispatch/campaign/<int:campaign_id>/apply',
                type='http', auth='public', website=True, methods=['POST'],
                csrf=True)
    def dispatch_apply(self, campaign_id, access_token=None, **kw):
        employee = self._get_employee_from_token(access_token)
        if not employee:
            return request.render('dispatch_shift.portal_invalid_token')

        campaign = request.env['dispatch.campaign'].sudo().browse(campaign_id)
        if not campaign.exists() or campaign.state != 'open':
            return request.redirect('/dispatch/my?access_token=%s' % access_token)

        if employee in campaign.frozen_employee_ids:
            request.session['dispatch_error'] = _('You are blocked from applying to shifts in this campaign.')
            return request.redirect(
                '/dispatch/campaign/%d/browse?access_token=%s'
                % (campaign_id, access_token))

        # Collect selected slot IDs from form
        slot_ids = []
        for key, value in kw.items():
            if key.startswith('slot_') and value == 'on':
                try:
                    slot_ids.append(int(key.replace('slot_', '')))
                except ValueError:
                    pass

        if not slot_ids:
            request.session['dispatch_error'] = _('No slots selected.')
            return request.redirect(
                '/dispatch/campaign/%d/browse?access_token=%s'
                % (campaign_id, access_token))

        Application = request.env['dispatch.shift.application'].sudo()
        slots = request.env['dispatch.shift.slot'].sudo().browse(slot_ids).exists()

        # Validate consecutive days
        new_dates = [s.date for s in slots]
        try:
            Application._check_consecutive_days(employee, campaign, new_dates)
        except ValidationError as e:
            request.session['dispatch_error'] = e.args[0]
            return request.redirect(
                '/dispatch/campaign/%d/browse?access_token=%s'
                % (campaign_id, access_token))

        # Validate time overlaps and create applications
        created = 0
        errors = []
        for slot in slots:
            # Skip if already applied or rejected
            existing = Application.search([
                ('employee_id', '=', employee.id),
                ('slot_id', '=', slot.id),
                ('state', 'in', ('applied', 'confirmed', 'waitlisted', 'rejected')),
            ], limit=1)
            if existing:
                continue

            try:
                Application._check_no_time_overlap(employee, slot)
            except ValidationError as e:
                errors.append(str(e.args[0]))
                continue

            Application.create({
                'employee_id': employee.id,
                'slot_id': slot.id,
            })
            created += 1

        if errors:
            request.session['dispatch_error'] = '; '.join(errors)
            return request.redirect(
                '/dispatch/campaign/%d/browse?access_token=%s'
                % (campaign_id, access_token))

        request.session['dispatch_message'] = _('%d shift(s) applied successfully.', created)
        return request.redirect('/dispatch/my?access_token=%s' % access_token)

    @http.route('/dispatch/application/<int:application_id>',
                type='http', auth='public', website=True)
    def dispatch_application_detail(self, application_id, access_token=None, **kw):
        employee = self._get_employee_from_token(access_token)
        if not employee:
            return request.render('dispatch_shift.portal_invalid_token')

        application = request.env['dispatch.shift.application'].sudo().browse(application_id)
        if not application.exists() or application.employee_id.id != employee.id:
            return request.redirect('/dispatch/my?access_token=%s' % access_token)

        application._portal_ensure_token()

        labels = {
            'shift_application': _('Shift Application'),
            'back': _('Back'),
            'date': _('Date'),
            'store': _('Store'),
            'shift': _('Shift'),
            'time': _('Time'),
            'campaign': _('Campaign'),
            'applied_at': _('Applied'),
            'status': _('Status'),
            'applied': _('Applied'),
            'confirmed': _('Confirmed'),
            'waitlisted': _('Waitlisted'),
            'rejected': _('Rejected'),
            'cancelled': _('Cancelled'),
            'cancel_application': _('Cancel Application'),
            'cancel_confirm': _('Cancel this shift?'),
            'communication_history': _('Communication History'),
        }

        return request.render('dispatch_shift.portal_application_detail', {
            'application': application,
            'employee': employee,
            'access_token': access_token,
            'shift_labels': self._get_shift_labels(),
            'format_hour': self._format_hour,
            'labels': labels,
        })

    @http.route('/dispatch/application/<int:application_id>/cancel',
                type='http', auth='public', website=True, methods=['POST'],
                csrf=True)
    def dispatch_cancel(self, application_id, access_token=None, **kw):
        employee = self._get_employee_from_token(access_token)
        if not employee:
            return request.render('dispatch_shift.portal_invalid_token')

        application = request.env['dispatch.shift.application'].sudo().browse(application_id)
        if not application.exists() or application.employee_id.id != employee.id:
            return request.redirect('/dispatch/my?access_token=%s' % access_token)

        application.action_cancel()
        request.session['dispatch_message'] = _('Shift cancelled.')
        return request.redirect('/dispatch/my?access_token=%s' % access_token)
