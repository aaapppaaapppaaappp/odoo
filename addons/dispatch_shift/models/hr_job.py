from odoo import api, fields, models, _


class HrJob(models.Model):
    _inherit = 'hr.job'

    dispatch_campaign_ids = fields.One2many(
        'dispatch.campaign', 'job_id', string='Dispatch Campaigns')
    dispatch_campaign_count = fields.Integer(
        compute='_compute_dispatch_campaign_count')

    @api.depends('dispatch_campaign_ids')
    def _compute_dispatch_campaign_count(self):
        campaign_data = self.env['dispatch.campaign']._read_group(
            [('job_id', 'in', self.ids)],
            ['job_id'],
            ['__count'],
        )
        mapped = {job.id: count for job, count in campaign_data}
        for job in self:
            job.dispatch_campaign_count = mapped.get(job.id, 0)

    def action_view_dispatch_campaigns(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Dispatch Campaigns'),
            'res_model': 'dispatch.campaign',
            'view_mode': 'list,form',
            'domain': [('job_id', '=', self.id)],
            'context': {'default_job_id': self.id},
        }
        if self.dispatch_campaign_count == 1:
            action['view_mode'] = 'form'
            action['res_id'] = self.dispatch_campaign_ids.id
        return action
