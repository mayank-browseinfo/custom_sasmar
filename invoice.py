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


class account_invoice_line(osv.osv):
    _inherit = "account.invoice.line"
    
    def _anglo_saxon_sale_move_lines(self, cr, uid, i_line, res, context=None):
        """Return the additional move lines for sales invoices and refunds.

        i_line: An account.invoice.line object.
        res: The move line entries produced so far by the parent move_line_get.
        """
        inv = i_line.invoice_id
        Property_obj = self.pool.get('ir.property')
        Field_obj = self.pool.get('ir.model.fields')
        Account_obj = self.pool.get('account.account')
        
        fiscal_pool = self.pool.get('account.fiscal.position')
        fpos = inv.fiscal_position or False
        dacc = False
        cacc = False
        company_currency = inv.company_id.currency_id.id
        print '\n custom valuation _anglo_saxon_sale_move_lines of acc anglo saxon',i_line.product_id.valuation,res,context,i_line,i_line.company_id
        if i_line.product_id.type != 'service' and i_line.product_id.valuation == 'real_time':
            # debit account dacc will be the output account
            # first check the product, if empty check the category

            field_id = Field_obj.search(cr, uid, [('field_description', '=', 'Stock Output Account'), ('name', '=', 'property_stock_account_output')])
            if field_id:
                property_id = Property_obj.search(cr, uid, [('fields_id', '=', field_id[0]), ('company_id', '=', i_line.company_id.id)])
            if property_id:
                acc_ref = Property_obj.browse(cr, uid, property_id[0]).value_reference
                dacc = acc_ref and acc_ref.split(',') and acc_ref.split(',')[1]
            if not dacc:
                field_id = Field_obj.search(cr, uid, [('field_description', '=', 'Stock Output Account'), ('name', '=', 'property_stock_account_output_categ')])
                if field_id:
                    property_id = Property_obj.search(cr, uid, [('fields_id', '=', field_id[0]), ('company_id', '=', i_line.company_id.id)])
                if property_id:
                    acc_ref = Property_obj.browse(cr, uid, property_id[0]).value_reference
                    dacc = acc_ref and acc_ref.split(',') and acc_ref.split(',')[1]
            
            # in both cases the credit account cacc will be the expense account
            # first check the product, if empty check the category
            
            field_id = Field_obj.search(cr, uid, [('field_description', '=', 'Expense Account'), ('name', '=', 'property_account_expense')])
            if field_id:
                property_id = Property_obj.search(cr, uid, [('fields_id', '=', field_id[0]), ('company_id', '=', i_line.company_id.id)])
            if property_id:
                acc_ref = Property_obj.browse(cr, uid, property_id[0]).value_reference
                cacc = acc_ref and acc_ref.split(',') and acc_ref.split(',')[1]
            if not cacc:
                field_id = Field_obj.search(cr, uid, [('field_description', '=', 'Expense Account'), ('name', '=', 'property_account_expense_categ')])
                if field_id:
                    property_id = Property_obj.search(cr, uid, [('fields_id', '=', field_id[0]), ('company_id', '=', i_line.company_id.id)])
                if property_id:
                    acc_ref = Property_obj.browse(cr, uid, property_id[0]).value_reference
                    cacc = acc_ref and acc_ref.split(',') and acc_ref.split(',')[1]
            
            print '\n \n dacc an cacc',dacc,cacc
            if dacc and cacc:
                price_unit = i_line.move_id and i_line.move_id.price_unit or i_line.product_id.standard_price
                return [
                    {
                        'type':'src',
                        'name': i_line.name[:64],
                        'price_unit':price_unit,
                        'quantity':i_line.quantity,
                        'price':self._get_price(cr, uid, inv, company_currency, i_line, price_unit),
                        'account_id': int(dacc),
                        'product_id':i_line.product_id.id,
                        'uos_id':i_line.uos_id.id,
                        'account_analytic_id': False,
                        'taxes':i_line.invoice_line_tax_id,
                    },

                    {
                        'type':'src',
                        'name': i_line.name[:64],
                        'price_unit':price_unit,
                        'quantity':i_line.quantity,
                        'price': -1 * self._get_price(cr, uid, inv, company_currency, i_line, price_unit),
                        'account_id':fiscal_pool.map_account(cr, uid, fpos, int(cacc)),
                        'product_id':i_line.product_id.id,
                        'uos_id':i_line.uos_id.id,
                        'account_analytic_id': False,
                        'taxes':i_line.invoice_line_tax_id,
                    },
                ]
        return []    


class stock_quant(osv.osv):
    _inherit = "stock.quant"
    
    def _create_account_move_line(self, cr, uid, quants, move, credit_account_id, debit_account_id, journal_id, context=None):
        print '\n custom _create_account_move_line of stock acc',move,credit_account_id,debit_account_id,context
        #group quants by cost
#### UPDATE CONTEXT        
        context.update({'company_id': context.get('force_company')})
        quant_cost_qty = {}
        for quant in quants:
            if quant_cost_qty.get(quant.cost):
                quant_cost_qty[quant.cost] += quant.qty
            else:
                quant_cost_qty[quant.cost] = quant.qty
        move_obj = self.pool.get('account.move')
        for cost, qty in quant_cost_qty.items():
            move_lines = self._prepare_account_move_line(cr, uid, move, qty, cost, credit_account_id, debit_account_id, context=context)
            period_id = context.get('force_period', self.pool.get('account.period').find(cr, uid, move.date, context=context)[0])
            print '\n period of _create_account_move_line',period_id
            move_obj.create(cr, uid, {'journal_id': journal_id,
                                      'line_id': move_lines,
                                      'period_id': period_id,
                                      'date': move.date,
                                      'ref': move.picking_id.name}, context=context)    


class account_move(osv.osv):
    _inherit = "account.move"
    
    def create(self, cr, uid, vals, context=None):
        if context.get('Purchase_key') == 'Purchase_key':
            vals.update({'company_id': context.get('force_company')})
        return super(account_move, self).create(cr, uid, vals, context=context)
