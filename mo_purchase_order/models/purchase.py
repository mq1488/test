# -*- coding: utf-8 -*-
from openerp import models, _
from openerp import SUPERUSER_ID
from datetime import datetime
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
import logging

_logger = logging.getLogger(__name__)


class procurement_order(models.Model):
    _inherit = 'procurement.order'

    def make_po(self, cr, uid, ids, context=None):
        res = {}
        company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
        po_obj = self.pool.get('purchase.order')
        po_line_obj = self.pool.get('purchase.order.line')
        seq_obj = self.pool.get('ir.sequence')
        pass_ids = []
        linked_po_ids = []
        sum_po_line_ids = []
        zodiac_po_line_ids = []
        zodiac_products_names = "Zodiac Birthstone"
        for procurement in self.browse(cr, uid, ids, context=context):
            engraved_word = False
            three_pendants_option = False
            proc_id = procurement.id
            sale_line_id_test = self.pool.get('procurement.order').browse(cr, uid, proc_id - 1, context=context).sale_line_id
            sale_line_id = self.pool.get('procurement.order').browse(cr, uid, proc_id - 1, context=context).sale_line_id.id
            group_id = procurement.group_id.id
            product_id = procurement.product_id.id
            order_name = str(procurement.origin).split(':')[0]
            associated_procurement_id = self.pool.get('procurement.order').search(cr, uid, [('group_id', '=', group_id),
                                                                                            ('origin', '=', order_name),
                                                                                            ('product_id', '=',
                                                                                             product_id), (
                                                                                            'sale_line_id', '=',
                                                                                            sale_line_id)],
                                                                                  context=context)[0]
            procurement_name = self.pool.get('procurement.order').browse(cr, uid, associated_procurement_id,
                                                                         context=context).name
            solid_gold = False
            hero_product = False
            foil = False
            laser_engraving = False
            stein = False
            stein_desc = ''
            if 'Stein_1' in procurement_name or 'Stein_2' in procurement_name:
                stein = True
                stein_desc = procurement_name
            if 'Engraving' in procurement_name:
                mark_1 = procurement_name.find("Engraving: ")
                rest_name = procurement_name[mark_1 + 11:]
                mark_2 = rest_name.find(" ||")
                engraved_word = rest_name[:mark_2]
            if 'Three pendants' in procurement_name:
                mark_1 = procurement_name.find("Three pendants: ")
                rest_name = procurement_name[mark_1 + 16:]
                mark_2 = rest_name.find(" ||")
                three_pendants_option = rest_name[:mark_2]
            ctx_company = dict(context or {}, force_company=procurement.company_id.id)
            partner = self._get_product_supplier(cr, uid, procurement, context=context)
            if not partner:
                self.message_post(cr, uid, [procurement.id],
                                  _('There is no supplier associated to product %s') % (procurement.product_id.name))
                res[procurement.id] = False
            else:
                schedule_date = self._get_purchase_schedule_date(cr, uid, procurement, company, context=context)
                purchase_date = self._get_purchase_order_date(cr, uid, procurement, company, schedule_date,
                                                              context=context)
                _logger.info('Sale line: %s %s %s',
                             sale_line_id_test.id,sale_line_id_test.order_id.id, sale_line_id_test.discount)

                if procurement.sale_line_id.discount >= 50:
                    line_vals = self._get_po_line_values_from_proc(cr, uid, procurement, partner, company,
                                                                   schedule_date, context=ctx_company)
                    # look for any other draft PO for the same supplier, to attach the new line on instead of creating a new draft one
                    date_start = '{} 00:00:01'.format(datetime.now().date())
                    date_end = '{} 23:59:59'.format(datetime.now().date())
                    available_draft_po_ids = po_obj.search(cr, uid, [
                        ('partner_id', '=', partner.id), ('state', '=', 'draft'),
                        ('picking_type_id', '=', procurement.rule_id.picking_type_id.id),
                        ('location_id', '=', procurement.location_id.id),
                        ('company_id', '=', procurement.company_id.id),
                        ('dest_address_id', '=', procurement.partner_dest_id.id),
                        ('is_discount', '=', True),
                        ('create_date', '>=', '{}'.format(datetime.strptime(date_start,(DEFAULT_SERVER_DATETIME_FORMAT)))),
                        ('create_date', '<=', '{}'.format(datetime.strptime(date_end,(DEFAULT_SERVER_DATETIME_FORMAT))))], context=context)
                    po_draft = 0
                    if available_draft_po_ids:
                        for draft in available_draft_po_ids:
                            available = 0
                            po_id = draft
                            po_rec = po_obj.browse(cr, uid, po_id, context=context)
                            for line in po_rec:
                                if line.product_id.name.find(zodiac_products_names) == -1:
                                    available += 1
                            if available != 0:
                                po_draft = po_id
                    if po_draft != 0 and partner.name != 'Merkle':
                        po_id = po_draft
                        po_rec = po_obj.browse(cr, uid, po_id, context=context)
                        po_to_update = {}
                        # if the product has to be ordered earlier those in the existing PO, we replace the purchase date on the order to avoid ordering it too late
                        if datetime.strptime(po_rec.date_order, DEFAULT_SERVER_DATETIME_FORMAT) > purchase_date:
                            po_obj.write(cr, uid, [po_id],
                                         {'date_order': purchase_date.strftime(DEFAULT_SERVER_DATETIME_FORMAT)},
                                         context=context)
                        # look for any other PO line in the selected PO with same product and UoM to sum quantities instead of creating a new po line
                        available_po_line_ids = po_line_obj.search(cr, uid, [('order_id', '=', po_id), (
                            'product_id', '=', line_vals['product_id']), ('product_uom', '=',
                                                                          line_vals['product_uom'])],
                                                                   context=context)
                        if available_po_line_ids and engraved_word is False and three_pendants_option is False and stein is False:
                            po_line = po_line_obj.browse(cr, uid, available_po_line_ids[0], context=context)
                            po_line_id = po_line.id
                            new_qty, new_price = self._calc_new_qty_price(cr, uid, procurement, po_line=po_line,
                                                                          context=context)

                            if new_qty > po_line.product_qty:
                                po_line_obj.write(cr, SUPERUSER_ID, po_line.id,
                                                  {'product_qty': new_qty, 'price_unit': new_price}, context=context)
                                sum_po_line_ids.append(procurement.id)
                        else:
                            line_vals.update(order_id=po_id)
                            po_line_id = po_line_obj.create(cr, SUPERUSER_ID, line_vals, context=context)
                            if engraved_word is not False:
                                po_line = po_line_obj.browse(cr, uid, po_line_id, context=context)[0]
                                name = po_line.name + " Engraving: " + engraved_word + ' ||'
                                po_line_obj.write(cr, SUPERUSER_ID, po_line.id, {'name': name}, context=context)
                            if three_pendants_option is not False:
                                po_line = po_line_obj.browse(cr, uid, po_line_id, context=context)[0]
                                name = po_line.name + " Three pendants: " + three_pendants_option + ' ||'
                                po_line_obj.write(cr, SUPERUSER_ID, po_line.id, {'name': name}, context=context)
                            if stein is not False:
                                po_line = po_line_obj.browse(cr, uid, po_line_id, context=context)[0]
                                name = stein_desc
                                po_line_obj.write(cr, SUPERUSER_ID, po_line.id, {'name': name}, context=context)
                            linked_po_ids.append(procurement.id)
                    else:
                        name = seq_obj.get(cr, uid, 'purchase.order') or _('PO: %s') % procurement.name
                        po_vals = {
                            'name': name,
                            'origin': procurement.origin,
                            'partner_id': partner.id,
                            'location_id': procurement.location_id.id,
                            'picking_type_id': procurement.rule_id.picking_type_id.id,
                            'pricelist_id': partner.property_product_pricelist_purchase.id,
                            'currency_id': partner.property_product_pricelist_purchase and partner.property_product_pricelist_purchase.currency_id.id or procurement.company_id.currency_id.id,
                            'date_order': purchase_date.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                            'company_id': procurement.company_id.id,
                            'fiscal_position': partner.property_account_position and partner.property_account_position.id or False,
                            'payment_term_id': partner.property_supplier_payment_term.id or False,
                            'dest_address_id': procurement.partner_dest_id.id,
                            'is_discount': True
                        }
                        po_id = self.create_procurement_purchase_order(cr, SUPERUSER_ID, procurement, po_vals,
                                                                       line_vals, context=context)
                        po_line_id = po_obj.browse(cr, uid, po_id, context=context).order_line[0].id
                        if engraved_word is not False:
                            po_line = po_line_obj.browse(cr, uid, po_line_id, context=context)[0]
                            name = po_line.name + " Engraving: " + engraved_word + ' ||'
                            po_line_obj.write(cr, SUPERUSER_ID, po_line.id, {'name': name}, context=context)
                        if three_pendants_option is not False:
                            po_line = po_line_obj.browse(cr, uid, po_line_id, context=context)[0]
                            name = po_line.name + " Three pendants: " + three_pendants_option + ' ||'
                            po_line_obj.write(cr, SUPERUSER_ID, po_line.id, {'name': name}, context=context)
                        if stein is not False:
                            po_line = po_line_obj.browse(cr, uid, po_line_id, context=context)[0]
                            name = stein_desc
                            po_line_obj.write(cr, SUPERUSER_ID, po_line.id, {'name': name}, context=context)
                        pass_ids.append(procurement.id)
                elif procurement.product_id.name.find(zodiac_products_names) != -1:
                    line_vals = self._get_po_line_values_from_proc(cr, uid, procurement, partner, company,
                                                                   schedule_date, context=ctx_company)
                    available_draft_po_ids = po_obj.search(cr, uid, [
                        ('partner_id', '=', partner.id), ('state', '=', 'draft'),
                        ('picking_type_id', '=', procurement.rule_id.picking_type_id.id),
                        ('location_id', '=', procurement.location_id.id),
                        ('company_id', '=', procurement.company_id.id),
                        ('is_discount', '=', False),
                        ('dest_address_id', '=', procurement.partner_dest_id.id)], context=context)
                    po_draft = 0
                    if available_draft_po_ids:
                        for draft in available_draft_po_ids:
                            available = 0
                            po_id = draft
                            po_rec = po_obj.browse(cr, uid, po_id, context=context)
                            for line in po_rec:
                                if line.product_id.name.find(zodiac_products_names) == -1:
                                    available += 1
                            if available == 0:
                                po_draft = po_id
                    if po_draft != 0 and partner.name != 'Merkle':
                        po_id = po_draft
                        po_rec = po_obj.browse(cr, uid, po_id, context=context)
                        po_to_update = {}
                        # if the product has to be ordered earlier those in the existing PO, we replace the purchase date on the order to avoid ordering it too late
                        if datetime.strptime(po_rec.date_order, DEFAULT_SERVER_DATETIME_FORMAT) > purchase_date:
                            po_obj.write(cr, uid, [po_id],
                                         {'date_order': purchase_date.strftime(DEFAULT_SERVER_DATETIME_FORMAT)},
                                         context=context)
                        # look for any other PO line in the selected PO with same product and UoM to sum quantities instead of creating a new po line
                        available_po_line_ids = po_line_obj.search(cr, uid, [('order_id', '=', po_id), (
                            'product_id', '=', line_vals['product_id']), ('product_uom', '=',
                                                                          line_vals['product_uom'])],
                                                                   context=context)
                        if available_po_line_ids and engraved_word is False and three_pendants_option is False and stein is False:
                            po_line = po_line_obj.browse(cr, uid, available_po_line_ids[0], context=context)
                            po_line_id = po_line.id
                            new_qty, new_price = self._calc_new_qty_price(cr, uid, procurement, po_line=po_line,
                                                                          context=context)

                            if new_qty > po_line.product_qty:
                                po_line_obj.write(cr, SUPERUSER_ID, po_line.id,
                                                  {'product_qty': new_qty, 'price_unit': new_price}, context=context)
                                zodiac_po_line_ids.append(procurement.id)
                        else:
                            line_vals.update(order_id=po_id)
                            po_line_id = po_line_obj.create(cr, SUPERUSER_ID, line_vals, context=context)
                            if engraved_word is not False:
                                po_line = po_line_obj.browse(cr, uid, po_line_id, context=context)[0]
                                name = po_line.name + " Engraving: " + engraved_word + ' ||'
                                po_line_obj.write(cr, SUPERUSER_ID, po_line.id, {'name': name}, context=context)
                            if three_pendants_option is not False:
                                po_line = po_line_obj.browse(cr, uid, po_line_id, context=context)[0]
                                name = po_line.name + " Three pendants: " + three_pendants_option + ' ||'
                                po_line_obj.write(cr, SUPERUSER_ID, po_line.id, {'name': name}, context=context)
                            if stein is not False:
                                po_line = po_line_obj.browse(cr, uid, po_line_id, context=context)[0]
                                name = stein_desc
                                po_line_obj.write(cr, SUPERUSER_ID, po_line.id, {'name': name}, context=context)
                            zodiac_po_line_ids.append(procurement.id)
                    else:
                        name = seq_obj.get(cr, uid, 'purchase.order') or _('PO: %s') % procurement.name
                        po_vals = {
                            'name': name,
                            'origin': procurement.origin,
                            'partner_id': partner.id,
                            'location_id': procurement.location_id.id,
                            'picking_type_id': procurement.rule_id.picking_type_id.id,
                            'pricelist_id': partner.property_product_pricelist_purchase.id,
                            'currency_id': partner.property_product_pricelist_purchase and partner.property_product_pricelist_purchase.currency_id.id or procurement.company_id.currency_id.id,
                            'date_order': purchase_date.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                            'company_id': procurement.company_id.id,
                            'fiscal_position': partner.property_account_position and partner.property_account_position.id or False,
                            'payment_term_id': partner.property_supplier_payment_term.id or False,
                            'dest_address_id': procurement.partner_dest_id.id,
                            'is_discount': False
                        }
                        po_id = self.create_procurement_purchase_order(cr, SUPERUSER_ID, procurement, po_vals,
                                                                       line_vals, context=context)
                        po_line_id = po_obj.browse(cr, uid, po_id, context=context).order_line[0].id
                        if engraved_word is not False:
                            po_line = po_line_obj.browse(cr, uid, po_line_id, context=context)[0]
                            name = po_line.name + " Engraving: " + engraved_word + ' ||'
                            po_line_obj.write(cr, SUPERUSER_ID, po_line.id, {'name': name}, context=context)
                        if three_pendants_option is not False:
                            po_line = po_line_obj.browse(cr, uid, po_line_id, context=context)[0]
                            name = po_line.name + " Three pendants: " + three_pendants_option + ' ||'
                            po_line_obj.write(cr, SUPERUSER_ID, po_line.id, {'name': name}, context=context)
                        if stein is not False:
                            po_line = po_line_obj.browse(cr, uid, po_line_id, context=context)[0]
                            name = stein_desc
                            po_line_obj.write(cr, SUPERUSER_ID, po_line.id, {'name': name}, context=context)
                        zodiac_po_line_ids.append(procurement.id)
                else:
                    line_vals = self._get_po_line_values_from_proc(cr, uid, procurement, partner, company,
                                                                   schedule_date, context=ctx_company)
                    # look for any other draft PO for the same supplier, to attach the new line on instead of creating a new draft one
                    available_draft_po_ids = po_obj.search(cr, uid, [
                        ('partner_id', '=', partner.id), ('state', '=', 'draft'),
                        ('picking_type_id', '=', procurement.rule_id.picking_type_id.id),
                        ('location_id', '=', procurement.location_id.id),
                        ('company_id', '=', procurement.company_id.id),
                        ('is_discount', '=', False),
                        ('dest_address_id', '=', procurement.partner_dest_id.id)
                    ], context=context)
                    po_draft = 0
                    if available_draft_po_ids:
                        for draft in available_draft_po_ids:
                            available = 0
                            po_id = draft
                            po_rec = po_obj.browse(cr, uid, po_id, context=context)
                            for line in po_rec:
                                if line.product_id.name.find(zodiac_products_names) == -1:
                                    available += 1
                            if available != 0:
                                po_draft = po_id
                    if po_draft != 0 and partner.name != 'Merkle':
                        po_id = po_draft
                        po_rec = po_obj.browse(cr, uid, po_id, context=context)
                        po_to_update = {}
                        # if the product has to be ordered earlier those in the existing PO, we replace the purchase date on the order to avoid ordering it too late
                        if datetime.strptime(po_rec.date_order, DEFAULT_SERVER_DATETIME_FORMAT) > purchase_date:
                            po_obj.write(cr, uid, [po_id],
                                         {'date_order': purchase_date.strftime(DEFAULT_SERVER_DATETIME_FORMAT)},
                                         context=context)
                        # look for any other PO line in the selected PO with same product and UoM to sum quantities instead of creating a new po line
                        available_po_line_ids = po_line_obj.search(cr, uid, [('order_id', '=', po_id), (
                        'product_id', '=', line_vals['product_id']), ('product_uom', '=', line_vals['product_uom'])],
                                                                   context=context)
                        if available_po_line_ids and engraved_word is False and three_pendants_option is False and stein is False:
                            po_line = po_line_obj.browse(cr, uid, available_po_line_ids[0], context=context)
                            po_line_id = po_line.id
                            new_qty, new_price = self._calc_new_qty_price(cr, uid, procurement, po_line=po_line,
                                                                          context=context)

                            if new_qty > po_line.product_qty:
                                po_line_obj.write(cr, SUPERUSER_ID, po_line.id,
                                                  {'product_qty': new_qty, 'price_unit': new_price}, context=context)
                                sum_po_line_ids.append(procurement.id)
                        else:
                            line_vals.update(order_id=po_id)
                            po_line_id = po_line_obj.create(cr, SUPERUSER_ID, line_vals, context=context)
                            if engraved_word is not False:
                                po_line = po_line_obj.browse(cr, uid, po_line_id, context=context)[0]
                                name = po_line.name + " Engraving: " + engraved_word + ' ||'
                                po_line_obj.write(cr, SUPERUSER_ID, po_line.id, {'name': name}, context=context)
                            if three_pendants_option is not False:
                                po_line = po_line_obj.browse(cr, uid, po_line_id, context=context)[0]
                                name = po_line.name + " Three pendants: " + three_pendants_option + ' ||'
                                po_line_obj.write(cr, SUPERUSER_ID, po_line.id, {'name': name}, context=context)
                            if stein is not False:
                                po_line = po_line_obj.browse(cr, uid, po_line_id, context=context)[0]
                                name = stein_desc
                                po_line_obj.write(cr, SUPERUSER_ID, po_line.id, {'name': name}, context=context)
                            linked_po_ids.append(procurement.id)
                    else:
                        name = seq_obj.get(cr, uid, 'purchase.order') or _('PO: %s') % procurement.name
                        po_vals = {
                            'name': name,
                            'origin': procurement.origin,
                            'partner_id': partner.id,
                            'location_id': procurement.location_id.id,
                            'picking_type_id': procurement.rule_id.picking_type_id.id,
                            'pricelist_id': partner.property_product_pricelist_purchase.id,
                            'currency_id': partner.property_product_pricelist_purchase and partner.property_product_pricelist_purchase.currency_id.id or procurement.company_id.currency_id.id,
                            'date_order': purchase_date.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                            'company_id': procurement.company_id.id,
                            'fiscal_position': partner.property_account_position and partner.property_account_position.id or False,
                            'payment_term_id': partner.property_supplier_payment_term.id or False,
                            'dest_address_id': procurement.partner_dest_id.id,
                            'is_discount': False
                        }
                        po_id = self.create_procurement_purchase_order(cr, SUPERUSER_ID, procurement, po_vals,
                                                                       line_vals, context=context)
                        po_line_id = po_obj.browse(cr, uid, po_id, context=context).order_line[0].id
                        if engraved_word is not False:
                            po_line = po_line_obj.browse(cr, uid, po_line_id, context=context)[0]
                            name = po_line.name + " Engraving: " + engraved_word + ' ||'
                            po_line_obj.write(cr, SUPERUSER_ID, po_line.id, {'name': name}, context=context)
                        if three_pendants_option is not False:
                            po_line = po_line_obj.browse(cr, uid, po_line_id, context=context)[0]
                            name = po_line.name + " Three pendants: " + three_pendants_option + ' ||'
                            po_line_obj.write(cr, SUPERUSER_ID, po_line.id, {'name': name}, context=context)
                        if stein is not False:
                            po_line = po_line_obj.browse(cr, uid, po_line_id, context=context)[0]
                            name = stein_desc
                            po_line_obj.write(cr, SUPERUSER_ID, po_line.id, {'name': name}, context=context)
                        pass_ids.append(procurement.id)
                res[procurement.id] = po_line_id
            self.write(cr, uid, [procurement.id], {'purchase_line_id': po_line_id}, context=context)
        if pass_ids:
            self.message_post(cr, uid, pass_ids, body=_("Draft Purchase Order created"), context=context)
        if linked_po_ids:
            self.message_post(cr, uid, linked_po_ids,
                              body=_("Purchase line created and linked to an existing Purchase Order"), context=context)
        if sum_po_line_ids:
            self.message_post(cr, uid, sum_po_line_ids, body=_("Quantity added in existing Purchase Order Line"),
                              context=context)
        if zodiac_po_line_ids:
            self.message_post(cr, uid, zodiac_po_line_ids, body=_("Draft Purchase Order created"), context=context)
        return res