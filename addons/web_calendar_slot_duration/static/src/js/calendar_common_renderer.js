/* Copyright 2023 Tecnativa - Stefan Ungureanu
 * License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl). */

import { CalendarCommonRenderer } from "@web/views/calendar/calendar_common/calendar_common_renderer";
import { patch } from "@web/core/utils/patch";

patch(CalendarCommonRenderer.prototype, {
    get options() {
        const options = super.options;
        const slotDuration = this.props.model.meta?.context?.calendar_slot_duration;
        if (slotDuration) {
            options.slotDuration = slotDuration;
        }
        return options;
    },
});
