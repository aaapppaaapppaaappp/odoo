from odoo import api, fields, models, _


class DispatchShiftSlot(models.Model):
    _name = 'dispatch.shift.slot'
    _description = 'Dispatch Shift Slot'
    _order = 'date, template_id'

    template_id = fields.Many2one(
        'dispatch.shift.template', string='Template',
        required=True, ondelete='cascade')
    campaign_id = fields.Many2one(
        'dispatch.campaign', string='Campaign',
        related='template_id.campaign_id', store=True, readonly=True)
    store_id = fields.Many2one(
        'res.partner', string='Store',
        related='template_id.store_id', store=True, readonly=True)
    shift_label = fields.Selection(
        related='template_id.shift_label', store=True, readonly=True)
    date = fields.Date('Date', required=True)
    start_hour = fields.Float('Start Hour', related='template_id.start_hour', readonly=True)
    end_hour = fields.Float('End Hour', related='template_id.end_hour', readonly=True)
    capacity = fields.Integer('Capacity', related='template_id.capacity', readonly=True)

    application_ids = fields.One2many(
        'dispatch.shift.application', 'slot_id', string='Applications')
    applied_count = fields.Integer(
        'Applied', compute='_compute_counts', store=True)
    confirmed_count = fields.Integer(
        'Confirmed', compute='_compute_counts', store=True)
    waitlisted_count = fields.Integer(
        'Waitlisted', compute='_compute_counts', store=True)
    seats_available = fields.Integer(
        'Available', compute='_compute_counts', store=True)
    is_full = fields.Boolean(
        'Full', compute='_compute_counts', store=True)

    _sql_constraints = [
        ('template_date_uniq', 'UNIQUE(template_id, date)',
         'A slot already exists for this template on this date.'),
    ]

    @api.depends('application_ids.state', 'template_id.capacity')
    def _compute_counts(self):
        for rec in self:
            applied = len(rec.application_ids.filtered(lambda a: a.state == 'applied'))
            confirmed = len(rec.application_ids.filtered(lambda a: a.state == 'confirmed'))
            waitlisted = len(rec.application_ids.filtered(lambda a: a.state == 'waitlisted'))
            rec.applied_count = applied
            rec.confirmed_count = confirmed
            rec.waitlisted_count = waitlisted
            rec.seats_available = max(0, rec.capacity - confirmed)
            rec.is_full = confirmed >= rec.capacity

    @api.depends('template_id.name', 'date')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s - %s' % (rec.date or '', rec.template_id.name or '')

    def _promote_waitlisted(self):
        for slot in self:
            confirmed = len(slot.application_ids.filtered(lambda a: a.state == 'confirmed'))
            available = max(0, slot.capacity - confirmed)
            if available <= 0:
                continue
            waitlisted = slot.application_ids.filtered(
                lambda a: a.state == 'waitlisted'
            ).sorted('applied_at')
            to_promote = waitlisted[:available]
            if to_promote:
                to_promote.write({'state': 'confirmed'})
