/** @odoo-module **/

document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('dispatch_apply_form');
    if (!form) return;

    form.addEventListener('submit', function (ev) {
        const checked = form.querySelectorAll('.dispatch-slot-cb:checked');
        if (checked.length === 0) {
            ev.preventDefault();
            alert('Please select at least one shift.');
            return;
        }
    });
});
