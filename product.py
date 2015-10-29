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
    
    
class product_template(osv.osv):
    _inherit = 'product.template'
        
    def get_product_accounts(self, cr, uid, product_id, context=None):
        """ To get the stock input account, stock output account and stock journal related to product.
        @param product_id: product id
        @return: dictionary which contains information regarding stock input account, stock output account and stock journal
        """
        if context is None:
            context = {}
        Property_obj = self.pool.get('ir.property')
        Field_obj = self.pool.get('ir.model.fields')
        Account_obj = self.pool.get('account.account')
        
        product_obj = self.browse(cr, uid, product_id, context=context)
        print '\n custom get_product_accounts',product_obj,context

#### TO GET Stock Input Account FOR COMPANY IN SALE ORDER        
        field_id = Field_obj.search(cr, uid, [('field_description', '=', 'Stock Input Account'), ('name', '=', 'property_stock_account_input')])
        if field_id:
            property_id = Property_obj.search(cr, uid, [('fields_id', '=', field_id[0]), ('company_id', '=', context.get('force_company'))])
        if property_id:
            acc_ref = Property_obj.browse(cr, uid, property_id[0]).value_reference
            stock_input_acc = acc_ref and acc_ref.split(',') and acc_ref.split(',')[1]
            stock_input_acc = int(stock_input_acc)
        else:
            stock_input_acc = False
        if not stock_input_acc:
            field_id = Field_obj.search(cr, uid, [('field_description', '=', 'Stock Input Account'), ('name', '=', 'property_stock_account_input_categ')])
            if field_id:
                property_id = Property_obj.search(cr, uid, [('fields_id', '=', field_id[0]), ('company_id', '=', context.get('force_company'))])
            if property_id:
                acc_ref = Property_obj.browse(cr, uid, property_id[0]).value_reference
                stock_input_acc = acc_ref and acc_ref.split(',') and acc_ref.split(',')[1]
                stock_input_acc = int(stock_input_acc)
                            

#### TO GET Stock Output Account FOR COMPANY IN PURCHASE ORDER
        field_id = Field_obj.search(cr, uid, [('field_description', '=', 'Stock Output Account'), ('name', '=', 'property_stock_account_output')])
        if field_id:
            property_id = Property_obj.search(cr, uid, [('fields_id', '=', field_id[0]), ('company_id', '=', context.get('force_company'))])
        if property_id:
            acc_ref = Property_obj.browse(cr, uid, property_id[0]).value_reference
            stock_output_acc = acc_ref and acc_ref.split(',') and acc_ref.split(',')[1]
            stock_output_acc = int(stock_output_acc)
        else:
            stock_output_acc = False
        if not stock_output_acc:
            field_id = Field_obj.search(cr, uid, [('field_description', '=', 'Stock Output Account'), ('name', '=', 'property_stock_account_output_categ')])
            if field_id:
                property_id = Property_obj.search(cr, uid, [('fields_id', '=', field_id[0]), ('company_id', '=', context.get('force_company'))])
            if property_id:
                acc_ref = Property_obj.browse(cr, uid, property_id[0]).value_reference
                stock_output_acc = acc_ref and acc_ref.split(',') and acc_ref.split(',')[1]
                stock_output_acc = int(stock_output_acc)

####### TO GET Stock Valuation Account FOR REQUIRED COMPANY

        field_id = Field_obj.search(cr, uid, [('field_description', '=', 'Stock Valuation Account'), ('name', '=', 'property_stock_valuation_account_id')])
        if field_id:
            property_id = Property_obj.search(cr, uid, [('fields_id', '=', field_id[0]), ('company_id', '=', context.get('force_company'))])
        if property_id:
            acc_ref = Property_obj.browse(cr, uid, property_id[0]).value_reference
            account_valuation = acc_ref and acc_ref.split(',') and acc_ref.split(',')[1]
            account_valuation = int(account_valuation)
        else:
            account_valuation = False
###########
                            
        journal_id = product_obj.categ_id.property_stock_journal and product_obj.categ_id.property_stock_journal.id or False

        if not all([stock_input_acc, stock_output_acc, account_valuation, journal_id]):
            raise osv.except_osv(_('Error!'), _('''One of the following information is missing on the product or product category and prevents the accounting valuation entries to be created:
    Product: %s
    Stock Input Account: %s
    Stock Output Account: %s
    Stock Valuation Account: %s
    Stock Journal: %s
    ''') % (product_obj.name, stock_input_acc, stock_output_acc, account_valuation, journal_id))
        return {
            'stock_account_input': stock_input_acc,
            'stock_account_output': stock_output_acc,
            'stock_journal': journal_id,
            'property_stock_valuation_account_id': account_valuation
        }
