from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class DispatchShiftApplication(models.Model):
    _name = 'dispatch.shift.application'
    _description = 'Dispatch Shift Application'
    _inherit = ['mail.thread', 'portal.mixin']
    _order = 'applied_at desc'
    _mail_post_access = 'read'

    employee_id = fields.Many2one(
        'hr.employee', string='Employee',
        required=True, ondelete='cascade')
    slot_id = fields.Many2one(
        'dispatch.shift.slot', string='Slot',
        required=True, ondelete='cascade')
    state = fields.Selection([
        ('applied', 'Applied'),
        ('confirmed', 'Confirmed'),
        ('waitlisted', 'Waitlisted'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='applied', required=True, tracking=True)
    applied_at = fields.Datetime('Applied At', default=fields.Datetime.now, readonly=True)

    # Related fields for display
    slot_date = fields.Date(related='slot_id.date', store=True, string='Date')
    store_id = fields.Many2one(related='slot_id.store_id', store=True, string='Store')
    campaign_id = fields.Many2one(related='slot_id.campaign_id', store=True, string='Campaign')
    is_frozen = fields.Boolean(
        'Frozen', compute='_compute_is_frozen')

    @api.depends('employee_id', 'campaign_id', 'campaign_id.frozen_employee_ids')
    def _compute_is_frozen(self):
        for app in self:
            app.is_frozen = app.employee_id in app.campaign_id.frozen_employee_ids

    _sql_constraints = [
        ('employee_slot_uniq', 'UNIQUE(employee_id, slot_id)',
         'An employee can only apply once per slot.'),
    ]

    @api.constrains('employee_id', 'slot_id')
    def _check_not_frozen(self):
        for app in self:
            campaign = app.slot_id.campaign_id
            if app.employee_id in campaign.frozen_employee_ids:
                raise ValidationError(
                    _('Employee %s is frozen from campaign %s and cannot apply.',
                      app.employee_id.name, campaign.name))

    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = '/dispatch/application/%s' % rec.id

    @api.depends('employee_id.name', 'slot_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s - %s' % (
                rec.employee_id.name or '',
                rec.slot_id.display_name or '',
            )

    def _check_consecutive_days(self, employee, campaign, new_dates):
        """Validate max consecutive days rule across all campaigns.
        new_dates is a set of date objects being applied for.
        """
        max_days = campaign.max_consecutive_days
        if not max_days:
            return

        existing = self.search([
            ('employee_id', '=', employee.id),
            ('state', 'in', ('applied', 'confirmed', 'waitlisted')),
        ])
        existing_dates = set(existing.mapped('slot_id.date'))
        all_dates = sorted(existing_dates | set(new_dates))

        if not all_dates:
            return

        consecutive = 1
        for i in range(1, len(all_dates)):
            if all_dates[i] - all_dates[i - 1] == timedelta(days=1):
                consecutive += 1
                if consecutive > max_days:
                    raise ValidationError(
                        _('Cannot work more than %d consecutive days. '
                          'Please adjust your selection.', max_days))
            else:
                consecutive = 1

    def _check_no_time_overlap(self, employee, slot):
        """Prevent double-booking: same employee, same date, overlapping hours."""
        existing = self.search([
            ('employee_id', '=', employee.id),
            ('slot_id.date', '=', slot.date),
            ('state', 'in', ('applied', 'confirmed', 'waitlisted')),
            ('slot_id', '!=', slot.id),
        ])
        for app in existing:
            other = app.slot_id
            if slot.start_hour < other.end_hour and slot.end_hour > other.start_hour:
                raise ValidationError(
                    _('Time overlap: you already have a shift from %(start)s to %(end)s on %(date)s.',
                      start='%d:%02d' % (int(other.start_hour), int(other.start_hour % 1 * 60)),
                      end='%d:%02d' % (int(other.end_hour), int(other.end_hour % 1 * 60)),
                      date=slot.date))

    def action_confirm(self):
        for app in self:
            if app.state != 'applied':
                continue
            slot = app.slot_id
            confirmed = len(slot.application_ids.filtered(lambda a: a.state == 'confirmed'))
            if confirmed < slot.capacity:
                app.write({'state': 'confirmed'})
                app.message_post(
                    body=_('Application confirmed.'),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
            else:
                app.write({'state': 'waitlisted'})
                app.message_post(
                    body=_('Slot is full. Application moved to waitlist.'),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )

    def action_reject_campaign(self):
        self.ensure_one()
        employee = self.employee_id
        campaign = self.campaign_id
        apps = self.search([
            ('employee_id', '=', employee.id),
            ('campaign_id', '=', campaign.id),
            ('state', 'in', ('applied', 'confirmed', 'waitlisted')),
        ])
        apps.action_reject()
        campaign.write({'frozen_employee_ids': [(4, employee.id)]})
        campaign.message_post(
            body=_('Employee %s has been frozen from this campaign.', employee.name),
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )

    def action_unfreeze_campaign(self):
        self.ensure_one()
        employee = self.employee_id
        campaign = self.campaign_id
        if employee in campaign.frozen_employee_ids:
            campaign.write({'frozen_employee_ids': [(3, employee.id)]})
            campaign.message_post(
                body=_('Employee %s has been unfrozen from this campaign.', employee.name),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

    def action_reject(self):
        was_confirmed = self.filtered(lambda a: a.state == 'confirmed')
        self.write({'state': 'rejected'})
        for app in self:
            app.message_post(
                body=_('Application rejected.'),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
        if was_confirmed:
            was_confirmed.mapped('slot_id')._promote_waitlisted()

    def action_release(self):
        """Release a rejected application so the employee can reapply to the slot."""
        for app in self.filtered(lambda a: a.state == 'rejected'):
            app.slot_id.message_post(
                body=_('Rejected application for %s has been released.', app.employee_id.name),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
        self.filtered(lambda a: a.state == 'rejected').unlink()

    def action_cancel(self):
        was_confirmed = self.filtered(lambda a: a.state == 'confirmed')
        self.write({'state': 'cancelled'})
        for app in self:
            app.message_post(
                body=_('Application cancelled.'),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
        if was_confirmed:
            was_confirmed.mapped('slot_id')._promote_waitlisted()
