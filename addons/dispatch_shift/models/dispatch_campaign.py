from datetime import timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_tzs = [(tz, tz) for tz in sorted(pytz.all_timezones, key=lambda tz: tz if not tz.startswith('Etc/') else '_')]


class DispatchCampaign(models.Model):
    _name = 'dispatch.campaign'
    _description = 'Dispatch Campaign'
    _inherit = ['mail.thread']
    _order = 'date_start desc, id desc'

    name = fields.Char('Name', required=True, tracking=True)
    job_id = fields.Many2one('hr.job', string='Job Position', tracking=True)
    client_id = fields.Many2one('res.partner', string='Client', tracking=True)
    date_start = fields.Date('Start Date', required=True, tracking=True)
    date_end = fields.Date('End Date', required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, tracking=True)
    max_consecutive_days = fields.Integer(
        'Max Consecutive Days', default=5,
        help='Maximum number of consecutive working days allowed for an employee.')
    timezone = fields.Selection(
        '_tz_get', string='Timezone', default='Asia/Taipei', required=True)
    invite_only = fields.Boolean(
        'Invite Only', default=False, tracking=True,
        help='When enabled, only invited employees can see this campaign in their portal.')
    invited_employee_ids = fields.Many2many(
        'hr.employee', 'dispatch_campaign_invited_employee_rel',
        'campaign_id', 'employee_id', string='Invited Employees')
    frozen_employee_ids = fields.Many2many(
        'hr.employee', 'dispatch_campaign_frozen_employee_rel',
        'campaign_id', 'employee_id', string='Frozen Employees',
        help='Employees who are blocked from applying to shifts in this campaign.')

    template_ids = fields.One2many(
        'dispatch.shift.template', 'campaign_id', string='Shift Templates')
    slot_ids = fields.One2many(
        'dispatch.shift.slot', 'campaign_id', string='Slots')

    template_count = fields.Integer(compute='_compute_template_count')
    slot_count = fields.Integer(compute='_compute_slot_count')
    invited_count = fields.Integer(compute='_compute_invited_count')
    frozen_count = fields.Integer(compute='_compute_frozen_count')

    @api.model
    def _tz_get(self):
        return _tzs

    @api.depends('template_ids')
    def _compute_template_count(self):
        for rec in self:
            rec.template_count = len(rec.template_ids)

    @api.depends('slot_ids')
    def _compute_slot_count(self):
        for rec in self:
            rec.slot_count = len(rec.slot_ids)

    @api.depends('invited_employee_ids')
    def _compute_invited_count(self):
        for rec in self:
            rec.invited_count = len(rec.invited_employee_ids)

    @api.depends('frozen_employee_ids')
    def _compute_frozen_count(self):
        for rec in self:
            rec.frozen_count = len(rec.frozen_employee_ids)

    def action_open(self):
        self.write({'state': 'open'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_invite_employees(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invite Employees'),
            'res_model': 'dispatch.campaign.invite',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_campaign_id': self.id},
        }

    def action_view_invited(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invited Employees'),
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.invited_employee_ids.ids)],
        }

    def action_view_frozen(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Frozen Employees'),
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.frozen_employee_ids.ids)],
        }

    def action_generate_slots(self):
        self.ensure_one()
        if not self.template_ids:
            raise UserError(_('Please add at least one shift template before generating slots.'))

        Slot = self.env['dispatch.shift.slot']
        current = self.date_start
        vals_list = []
        while current <= self.date_end:
            for template in self.template_ids:
                existing = Slot.search([
                    ('template_id', '=', template.id),
                    ('date', '=', current),
                ], limit=1)
                if not existing:
                    vals_list.append({
                        'template_id': template.id,
                        'campaign_id': self.id,
                        'date': current,
                    })
            current += timedelta(days=1)

        if vals_list:
            Slot.create(vals_list)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Slots Generated'),
                'message': _('%d slot(s) created.', len(vals_list)),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_view_templates(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Shift Templates'),
            'res_model': 'dispatch.shift.template',
            'view_mode': 'list,form',
            'domain': [('campaign_id', '=', self.id)],
            'context': {'default_campaign_id': self.id},
        }

    def action_view_slots(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Shift Slots'),
            'res_model': 'dispatch.shift.slot',
            'view_mode': 'list,calendar,form',
            'domain': [('campaign_id', '=', self.id)],
            'context': {'default_campaign_id': self.id},
        }
