from odoo import api, fields, models, _


class DispatchShiftTemplate(models.Model):
    _name = 'dispatch.shift.template'
    _description = 'Dispatch Shift Template'
    _order = 'campaign_id, store_id, start_hour'

    campaign_id = fields.Many2one(
        'dispatch.campaign', string='Campaign',
        required=True, ondelete='cascade')
    store_id = fields.Many2one(
        'res.partner', string='Store', required=True)
    shift_label = fields.Selection([
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon'),
        ('evening', 'Evening'),
    ], string='Shift', required=True)
    start_hour = fields.Float('Start Hour', required=True)
    end_hour = fields.Float('End Hour', required=True)
    capacity = fields.Integer('Capacity', default=2, required=True)

    name = fields.Char('Name', compute='_compute_name', store=True)

    slot_ids = fields.One2many(
        'dispatch.shift.slot', 'template_id', string='Slots')

    @api.depends('campaign_id.name', 'store_id.name', 'shift_label', 'start_hour', 'end_hour')
    def _compute_name(self):
        labels = dict(self._fields['shift_label'].selection)
        for rec in self:
            start = '%d:%02d' % (int(rec.start_hour), int(rec.start_hour % 1 * 60))
            end = '%d:%02d' % (int(rec.end_hour), int(rec.end_hour % 1 * 60))
            store = rec.store_id.name or ''
            label = labels.get(rec.shift_label, '')
            rec.name = '%s - %s (%s-%s)' % (store, label, start, end)
