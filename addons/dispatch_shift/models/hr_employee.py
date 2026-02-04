from odoo import api, fields, models, _


class HrEmployee(models.Model):
    _inherit = ['hr.employee', 'portal.mixin']

    dispatch_application_count = fields.Integer(
        'Dispatch Applications', compute='_compute_dispatch_application_count')

    def _compute_dispatch_application_count(self):
        data = self.env['dispatch.shift.application'].with_context(active_test=False)._read_group(
            [('employee_id', 'in', self.ids)],
            ['employee_id'],
            ['__count'],
        )
        mapped = {employee.id: count for employee, count in data}
        for rec in self:
            rec.dispatch_application_count = mapped.get(rec.id, 0)

    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = '/dispatch/my'

    def action_send_dispatch_link(self):
        self.ensure_one()
        self._portal_ensure_token()
        template = self.env.ref('dispatch_shift.mail_template_dispatch_employee_link')
        template.send_mail(self.id, force_send=True)

    def action_view_dispatch_applications(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Dispatch Applications'),
            'res_model': 'dispatch.shift.application',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
        }

    def _get_portal_url(self):
        self.ensure_one()
        return '/dispatch/my?access_token=%s' % self._portal_ensure_token()
