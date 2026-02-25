from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DispatchCampaignInvite(models.TransientModel):
    _name = 'dispatch.campaign.invite'
    _description = 'Invite Employees to Campaign'

    campaign_id = fields.Many2one(
        'dispatch.campaign', string='Campaign',
        required=True, ondelete='cascade')
    tag_ids = fields.Many2many(
        'hr.employee.category', string='Filter by Tags',
        help='Select tags to filter the employee list. Leave empty to show all.')
    employee_ids = fields.Many2many(
        'hr.employee', string='Employees',
        domain="[('active', '=', True)]")
    send_mail = fields.Boolean('Send Invitation Email', default=True)
    channel = fields.Selection([
        ('email', 'Email'),
    ], string='Channel', default='email', required=True)

    @api.onchange('tag_ids')
    def _onchange_tag_ids(self):
        if self.tag_ids:
            return {
                'domain': {
                    'employee_ids': [
                        ('active', '=', True),
                        ('category_ids', 'in', self.tag_ids.ids),
                    ],
                },
            }
        return {
            'domain': {
                'employee_ids': [('active', '=', True)],
            },
        }

    def action_add_all_filtered(self):
        self.ensure_one()
        domain = [('active', '=', True)]
        if self.tag_ids:
            domain.append(('category_ids', 'in', self.tag_ids.ids))
        employees = self.env['hr.employee'].search(domain)
        self.employee_ids = [(6, 0, employees.ids)]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invite Employees'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_invite(self):
        self.ensure_one()
        if not self.employee_ids:
            raise UserError(_('Please select at least one employee to invite.'))
        campaign = self.campaign_id

        # Add employees to invited list (idempotent via (4, id))
        campaign.write({
            'invited_employee_ids': [(4, emp.id) for emp in self.employee_ids],
        })

        if self.send_mail and self.channel == 'email':
            template = self.env.ref(
                'dispatch_shift.mail_template_dispatch_campaign_invite',
                raise_if_not_found=False,
            )
            if template:
                for employee in self.employee_ids:
                    employee._portal_ensure_token()
                    template.with_context(
                        campaign_id=campaign.id,
                        campaign_name=campaign.name,
                        lang=employee._dispatch_get_mail_lang(),
                    ).send_mail(employee.id, force_send=True)

        count = len(self.employee_ids)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Invitations Sent'),
                'message': _('%d employee(s) invited to %s.', count, campaign.name),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
