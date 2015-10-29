# -*- coding: utf-8 -*-
##############################################################################
#
#    This module uses OpenERP, Open Source Management Solution Framework.
#    Copyright (C) 2015-Today BrowseInfo (<http://www.browseinfo.in>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>
#
##############################################################################

from openerp.osv import fields, osv
from openerp.tools.translate import _

class sale_order(osv.osv):
    _inherit = "sale.order"
    
    def onchange_company_id(self, cr, uid, ids, company, context=None):
        Warehouse_obj = self.pool.get('stock.warehouse')
        warehouse = Warehouse_obj.search(cr, uid, [('company_id', '=', company)])
        if warehouse:
            return {'value': {'warehouse_id': warehouse[0]}}
        print '\n warehouse=====',warehouse
        return {}
    
    def action_invoice_create(self, cr, uid, ids, grouped=False, states=None, date_invoice = False, context=None):
        if not context:
            context = {}
        if states is None:
            states = ['confirmed', 'done', 'exception']
        res = False
        invoices = {}
        invoice_ids = []
        invoice = self.pool.get('account.invoice')
        obj_sale_order_line = self.pool.get('sale.order.line')
        partner_currency = {}
        # If date was specified, use it as date invoiced, usefull when invoices are generated this month and put the
        # last day of the last month as invoice date
        if date_invoice:
            context = dict(context or {}, date_invoice=date_invoice)
        for o in self.browse(cr, uid, ids, context=context):
            context.update({'sale_id':o})
            currency_id = o.pricelist_id.currency_id.id
            if (o.partner_id.id in partner_currency) and (partner_currency[o.partner_id.id] <> currency_id):
                raise osv.except_osv(
                    _('Error!'),
                    _('You cannot group sales having different currencies for the same partner.'))

            partner_currency[o.partner_id.id] = currency_id
            lines = []
            for line in o.order_line:
                if line.invoiced:
                    continue
                elif (line.state in states):
                    lines.append(line.id)
            created_lines = obj_sale_order_line.invoice_line_create(cr, uid, lines,context)
            if created_lines:
                invoices.setdefault(o.partner_invoice_id.id or o.partner_id.id, []).append((o, created_lines))
        if not invoices:
            for o in self.browse(cr, uid, ids, context=context):
                for i in o.invoice_ids:
                    if i.state == 'draft':
                        return i.id
        for val in invoices.values():
            if grouped:
                res = self._make_invoice(cr, uid, val[0][0], reduce(lambda x, y: x + y, [l for o, l in val], []), context=context)
                invoice_ref = ''
                origin_ref = ''
                for o, l in val:
                    invoice_ref += (o.client_order_ref or o.name) + '|'
                    origin_ref += (o.origin or o.name) + '|'
                    self.write(cr, uid, [o.id], {'state': 'progress'})
                    cr.execute('insert into sale_order_invoice_rel (order_id,invoice_id) values (%s,%s)', (o.id, res))
                    self.invalidate_cache(cr, uid, ['invoice_ids'], [o.id], context=context)
                #remove last '|' in invoice_ref
                if len(invoice_ref) >= 1:
                    invoice_ref = invoice_ref[:-1]
                if len(origin_ref) >= 1:
                    origin_ref = origin_ref[:-1]
                invoice.write(cr, uid, [res], {'origin': origin_ref, 'name': invoice_ref})
            else:
                for order, il in val:
                    res = self._make_invoice(cr, uid, order, il, context=context)
                    invoice_ids.append(res)
                    self.write(cr, uid, [order.id], {'state': 'progress'})
                    cr.execute('insert into sale_order_invoice_rel (order_id,invoice_id) values (%s,%s)', (order.id, res))
                    self.invalidate_cache(cr, uid, ['invoice_ids'], [order.id], context=context)
        return res

    def _prepare_invoice(self, cr, uid, order, lines, context=None):
        """Prepare the dict of values to create the new invoice for a
           sales order. This method may be overridden to implement custom
           invoice generation (making sure to call super() to establish
           a clean extension chain).

           :param browse_record order: sale.order record to invoice
           :param list(int) line: list of invoice line IDs that must be
                                  attached to the invoice
           :return: dict of value to create() the invoice
        """
        if context is None:
            context = {}
        Property_obj = self.pool.get('ir.property')
        Field_obj = self.pool.get('ir.model.fields')
        Account_obj = self.pool.get('account.account')
        account_id = False
        
        journal_ids = self.pool.get('account.journal').search(cr, uid,
            [('type', '=', 'sale'), ('company_id', '=', order.company_id.id)],
            limit=1)
        if not journal_ids:
            raise osv.except_osv(_('Error!'),
                _('Please define sales journal for this company: "%s" (id:%d).') % (order.company_id.name, order.company_id.id))
        
        field_id = Field_obj.search(cr, uid, [('field_description', '=', 'Account Receivable')])
        if field_id:
            property_id = Property_obj.search(cr, uid, [('fields_id', '=', field_id[0]), ('company_id', '=', order.company_id.id)])
        if property_id:
            acc_ref = Property_obj.browse(cr, uid, property_id[0]).value_reference
            account_id = acc_ref and acc_ref.split(',') and acc_ref.split(',')[1]
            account_id = int(account_id)
            
        invoice_vals = {
            'name': order.client_order_ref or '',
            'origin': order.name,
            'type': 'out_invoice',
            'reference': order.client_order_ref or order.name,
            'account_id': account_id or False,
            'partner_id': order.partner_invoice_id.id,
            'journal_id': journal_ids[0],
            'invoice_line': [(6, 0, lines)],
            'currency_id': order.pricelist_id.currency_id.id,
            'comment': order.note,
            'payment_term': order.payment_term and order.payment_term.id or False,
            'fiscal_position': order.fiscal_position.id or order.partner_invoice_id.property_account_position.id,
            'date_invoice': context.get('date_invoice', False),
            'company_id': order.company_id.id,
            'user_id': order.user_id and order.user_id.id or False,
            'section_id' : order.section_id.id
        }
        invoice_vals.update(self._inv_get(cr, uid, order, context=context))
        return invoice_vals

class sale_order_line(osv.osv):
    _inherit = 'sale.order.line'
    
    def _prepare_order_line_invoice_line(self, cr, uid, line, account_id=False, context=None):
        """Prepare the dict of values to create the new invoice line for a
           sales order line. This method may be overridden to implement custom
           invoice generation (making sure to call super() to establish
           a clean extension chain).

           :param browse_record line: sale.order.line record to invoice
           :param int account_id: optional ID of a G/L account to force
               (this is used for returning products including service)
           :return: dict of values to create() the invoice line
        """
        res = {}
        Property_obj = self.pool.get('ir.property')
        Field_obj = self.pool.get('ir.model.fields')
        Account_obj = self.pool.get('account.account')
        account_id = False
        if not line.invoiced:
            if not account_id:
                if line.product_id:
                    
                    field_id = Field_obj.search(cr, uid, [('field_description', '=', 'Income Account'), ('name', '=', 'property_account_income')])
                    if field_id:
                        property_id = Property_obj.search(cr, uid, [('fields_id', '=', field_id[0]), ('company_id', '=', context.get('sale_id').company_id.id)])
                    if property_id:
                        acc_ref = Property_obj.browse(cr, uid, property_id[0]).value_reference
                        account_id = acc_ref and acc_ref.split(',') and acc_ref.split(',')[1]
                        account_id = int(account_id)
                        
                    if not account_id:
                        field_id = Field_obj.search(cr, uid, [('field_description', '=', 'Income Account'), ('name', '=', 'property_account_income_categ')])
                        if field_id:
                            property_id = Property_obj.search(cr, uid, [('fields_id', '=', field_id[0]), ('company_id', '=', context.get('sale_id').company_id.id)])
                        if property_id:
                            acc_ref = Property_obj.browse(cr, uid, property_id[0]).value_reference
                            account_id = acc_ref and acc_ref.split(',') and acc_ref.split(',')[1]
                            account_id = int(account_id)
                    if not account_id:
                        raise osv.except_osv(_('Error!'),
                                _('Please define income account for this product: "%s" (id:%d).') % \
                                    (line.product_id.name, line.product_id.id,))
                        
                else:
                    prop = self.pool.get('ir.property').get(cr, uid,
                            'property_account_income_categ', 'product.category',
                            context=context)
                    account_id = prop and prop.id or False
            uosqty = self._get_line_qty(cr, uid, line, context=context)
            uos_id = self._get_line_uom(cr, uid, line, context=context)
            pu = 0.0
            if uosqty:
                pu = round(line.price_unit * line.product_uom_qty / uosqty,
                        self.pool.get('decimal.precision').precision_get(cr, uid, 'Product Price'))
            fpos = line.order_id.fiscal_position or False
            account_id = self.pool.get('account.fiscal.position').map_account(cr, uid, fpos, account_id)
            if not account_id:
                raise osv.except_osv(_('Error!'),
                            _('There is no Fiscal Position defined or Income category account defined for default properties of Product categories.'))
            res = {
                'name': line.name,
                'sequence': line.sequence,
                'origin': line.order_id.name,
                'account_id': account_id or False,
                'price_unit': pu,
                'quantity': uosqty,
                'discount': line.discount,
                'uos_id': uos_id,
                'product_id': line.product_id.id or False,
                'invoice_line_tax_id': [(6, 0, [x.id for x in line.tax_id])],
                'account_analytic_id': line.order_id.project_id and line.order_id.project_id.id or False,
            }

        return res
        # Care for deprecated _inv_get() hook - FIXME: to be removed after 6.1
        
class stock_move(osv.osv):
    _inherit = "stock.move"
    
    def _get_invoice_line_vals(self, cr, uid, move, partner, inv_type, context=None):
        print "context:::::::::;hello",context
        fp_obj = self.pool.get('account.fiscal.position')
        Property_obj = self.pool.get('ir.property')
        Field_obj = self.pool.get('ir.model.fields')
        Account_obj = self.pool.get('account.account')
        account_id = False
        # Get account_id
        if inv_type in ('out_invoice', 'out_refund'):
            
            field_id = Field_obj.search(cr, uid, [('field_description', '=', 'Income Account'), ('name', '=', 'property_account_income')])
            if field_id:
                property_id = Property_obj.search(cr, uid, [('fields_id', '=', field_id[0]), ('company_id', '=', context.get('company_id'))])
            if property_id:
                acc_ref = Property_obj.browse(cr, uid, property_id[0]).value_reference
                account_id = acc_ref and acc_ref.split(',') and acc_ref.split(',')[1]
                account_id = int(account_id)
            if not account_id:
                field_id = Field_obj.search(cr, uid, [('field_description', '=', 'Income Account'), ('name', '=', 'property_account_income_categ')])
                if field_id:
                    property_id = Property_obj.search(cr, uid, [('fields_id', '=', field_id[0]), ('company_id', '=', context.get('company_id'))])
                if property_id:
                    acc_ref = Property_obj.browse(cr, uid, property_id[0]).value_reference
                    account_id = acc_ref and acc_ref.split(',') and acc_ref.split(',')[1]
                    account_id = int(account_id)
                                        
        else:
            
            field_id = Field_obj.search(cr, uid, [('field_description', '=', 'Expense Account'), ('name', '=', 'property_account_expense')])
            if field_id:
                property_id = Property_obj.search(cr, uid, [('fields_id', '=', field_id[0]), ('company_id', '=', context.get('company_id'))])
            if property_id:
                acc_ref = Property_obj.browse(cr, uid, property_id[0]).value_reference
                account_id = acc_ref and acc_ref.split(',') and acc_ref.split(',')[1]
                account_id = int(account_id)
                
            if not account_id:
                field_id = Field_obj.search(cr, uid, [('field_description', '=', 'Expense Account'), ('name', '=', 'property_account_expense_categ')])
                if field_id:
                    property_id = Property_obj.search(cr, uid, [('fields_id', '=', field_id[0]), ('company_id', '=', context.get('company_id'))])
                if property_id:
                    acc_ref = Property_obj.browse(cr, uid, property_id[0]).value_reference
                    account_id = acc_ref and acc_ref.split(',') and acc_ref.split(',')[1]
                    account_id = int(account_id)
                                
        fiscal_position = partner.property_account_position
        account_id = fp_obj.map_account(cr, uid, fiscal_position, account_id)

        # set UoS if it's a sale and the picking doesn't have one
        uos_id = move.product_uom.id
        quantity = move.product_uom_qty
        if move.product_uos:
            uos_id = move.product_uos.id
            quantity = move.product_uos_qty

        taxes_ids = self._get_taxes(cr, uid, move, context=context)
        return {
            'name': move.name,
            'account_id': account_id or False,
            'product_id': move.product_id.id,
            'uos_id': uos_id,
            'quantity': quantity,
            'price_unit': self._get_price_unit_invoice(cr, uid, move, inv_type),
            'invoice_line_tax_id': [(6, 0, taxes_ids)],
            'discount': 0.0,
            'account_analytic_id': False,
        }
        
        
class stock_picking(osv.osv):
    _inherit = 'stock.picking'
    
    def action_invoice_create(self, cr, uid, ids, journal_id, group=False, type='out_invoice', context=None):
        """ Creates invoice based on the invoice state selected for picking.
        @param journal_id: Id of journal
        @param group: Whether to create a group invoice or not
        @param type: Type invoice to be created
        @return: Ids of created invoices for the pickings
        """
        context = context or {}
        todo = {}
        for picking in self.browse(cr, uid, ids, context=context):
            context.update({'company_id':picking.company_id.id})
            partner = self._get_partner_to_invoice(cr, uid, picking, context)
            #grouping is based on the invoiced partner
            if group:
                key = partner
            else:
                key = picking.id
            for move in picking.move_lines:
                if move.invoice_state == '2binvoiced':
                    if (move.state != 'cancel') and not move.scrapped:
                        todo.setdefault(key, [])
                        todo[key].append(move)
        invoices = []
        for moves in todo.values():
            invoices += self._invoice_create_line(cr, uid, moves, journal_id, type, context=context)
        return invoices
    
    def _get_invoice_vals(self, cr, uid, key, inv_type, journal_id, move, context=None):
        Property_obj = self.pool.get('ir.property')
        Field_obj = self.pool.get('ir.model.fields')
        Account_obj = self.pool.get('account.account')
        account_id = False
        
        if context is None:
            context = {}
        partner, currency_id, company_id, user_id = key
        if inv_type in ('out_invoice', 'out_refund'):
            field_id = Field_obj.search(cr, uid, [('field_description', '=', 'Account Receivable'), ('name', '=', 'property_account_receivable')])
            if field_id:
                property_id = Property_obj.search(cr, uid, [('fields_id', '=', field_id[0]), ('company_id', '=', company_id)])
            if property_id:
                acc_ref = Property_obj.browse(cr, uid, property_id[0]).value_reference
                account_id = acc_ref and acc_ref.split(',') and acc_ref.split(',')[1]
                account_id = int(account_id)
            
            payment_term = partner.property_payment_term.id or False
        else:
            field_id = Field_obj.search(cr, uid, [('field_description', '=', 'Account Payable'), ('name', '=', 'property_account_payable')])
            if field_id:
                property_id = Property_obj.search(cr, uid, [('fields_id', '=', field_id[0]), ('company_id', '=', company_id)])
            if property_id:
                acc_ref = Property_obj.browse(cr, uid, property_id[0]).value_reference
                account_id = acc_ref and acc_ref.split(',') and acc_ref.split(',')[1]
                account_id = int(account_id)
                
            payment_term = partner.property_supplier_payment_term.id or False
        return {
            'origin': move.picking_id.name,
            'date_invoice': context.get('date_inv', False),
            'user_id': user_id,
            'partner_id': partner.id,
            'account_id': account_id or False,
            'payment_term': payment_term,
            'type': inv_type,
            'fiscal_position': partner.property_account_position.id,
            'company_id': company_id,
            'currency_id': currency_id,
            'journal_id': journal_id,
        }
    _defaults = {
             'company_id': lambda self, cr, uid, context: context.get('company_id') 
             }

class stock_invoice_onshipping(osv.osv_memory):
    _inherit = 'stock.invoice.onshipping'
    
    def _get_journal(self, cr, uid, context=None):
        company_id = self.pool.get('stock.picking').browse(cr,uid,context.get('active_id')).company_id.id
        journal_obj = self.pool.get('account.journal')
        journal_type = self._get_journal_type(cr, uid, context=context)
        journals = journal_obj.search(cr, uid, [('type', '=', journal_type),('company_id','=',company_id)])
        return journals and journals[0] or False
    
    _defaults = {
        'journal_id' : _get_journal,
    }

class invoice(osv.osv):
    _inherit = 'account.invoice'

    def invoice_pay_customer(self, cr, uid, ids, context=None):
        if not ids: return []
        dummy, view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_voucher', 'view_vendor_receipt_dialog_form')

        inv = self.browse(cr, uid, ids[0], context=context)
        return {
            'name':_("Pay Invoice"),
            'view_mode': 'form',
            'view_id': view_id,
            'view_type': 'form',
            'res_model': 'account.voucher',
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]',
            'context': {
                'payment_expected_currency': inv.currency_id.id,
                'default_partner_id': self.pool.get('res.partner')._find_accounting_partner(inv.partner_id).id,
                'default_amount': inv.type in ('out_refund', 'in_refund') and -inv.residual or inv.residual,
                'default_reference': inv.name,
                'close_after_process': True,
                'invoice_type': inv.type,
                'invoice_id': inv.id,
                'default_type': inv.type in ('out_invoice','out_refund') and 'receipt' or 'payment',
                'type': inv.type in ('out_invoice','out_refund') and 'receipt' or 'payment',
                'company_id' : inv.company_id.id
            }
        }

class account_voucher(osv.osv):
    
    _inherit = 'account.voucher'
    
    _defaults = {
                 'company_id': lambda self, cr, uid, context: context.get('company_id') 
                 }

class purchsae_order(osv.osv):
    
    _inherit = 'purchase.order'
    
    def action_picking_create(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        for order in self.browse(cr, uid, ids):
            context.update({'company_id':order.company_id.id})
            picking_vals = {
                'picking_type_id': order.picking_type_id.id,
                'partner_id': order.partner_id.id,
                'date': order.date_order,
                'origin': order.name
            }
            picking_id = self.pool.get('stock.picking').create(cr, uid, picking_vals, context=context)
            self._create_stock_moves(cr, uid, order, order.order_line, picking_id, context=context)
        return picking_id
    
    def view_picking(self, cr, uid, ids, context=None):
        '''
        This function returns an action that display existing picking orders of given purchase order ids.
        '''
        if context is None:
            context = {}
        mod_obj = self.pool.get('ir.model.data')
        dummy, action_id = tuple(mod_obj.get_object_reference(cr, uid, 'stock', 'action_picking_tree'))
        action = self.pool.get('ir.actions.act_window').read(cr, uid, action_id, context=context)

        pick_ids = []
        for po in self.browse(cr, uid, ids, context=context):
            pick_ids += [picking.id for picking in po.picking_ids]

        #override the context to get rid of the default filtering on picking type
        action['context'] = {}
        #choose the view_mode accordingly
        if len(pick_ids) > 1:
            action['domain'] = "[('id','in',[" + ','.join(map(str, pick_ids)) + "])]"
        else:
            res = mod_obj.get_object_reference(cr, uid, 'stock', 'view_picking_form')
            action['views'] = [(res and res[1] or False, 'form')]
            action['res_id'] = pick_ids and pick_ids[0] or False
        context.update({'company_id':po.company_id.id})
        return action
