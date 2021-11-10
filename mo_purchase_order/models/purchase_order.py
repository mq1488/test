from openerp import models, _, fields
from openerp import SUPERUSER_ID
from datetime import datetime
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
import logging

_logger = logging.getLogger(__name__)


class purchase_order(models.Model):
    _inherit = 'purchase.order'

    is_discount = fields.Boolean()