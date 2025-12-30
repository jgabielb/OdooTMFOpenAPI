from odoo import http, fields
from odoo.http import request
import json

class TMFCatalogController(http.Controller):

    # =======================================================
    # 1. Product Specification API
    # =======================================================
    @http.route('/tmf-api/productCatalogManagement/v5/productSpecification', type='http', auth='public', methods=['GET'], csrf=False)
    def get_specifications(self, **params):
        """
        TMF620: List Product Specifications
        """
        # Fetch data
        specs = request.env['tmf.product.specification'].sudo().search([])
        
        response_data = []
        for s in specs:
            response_data.append({
                "id": s.tmf_id,
                "href": s.href,
                "name": s.name,
                "description": s.description or "",
                "productNumber": s.product_number or "",
                "brand": s.brand or "",
                "version": s.version,
                "lifecycleStatus": s.lifecycle_status,
                "@type": "ProductSpecification"
            })

        return request.make_response(
            json.dumps(response_data),
            headers=[('Content-Type', 'application/json')]
        )

    # =======================================================
    # 2. Product Offering API (The most important one)
    # =======================================================
    @http.route('/tmf-api/productCatalogManagement/v5/productOffering', type='http', auth='public', methods=['GET'], csrf=False)
    def get_offerings(self, **params):
        """
        TMF620: List Product Offerings (Commercial Products)
        """
        # Fetch Odoo Products (Templates)
        offerings = request.env['product.template'].sudo().search([('active', '=', True)])
        
        response_data = []
        for o in offerings:
            offering_json = {
                "id": o.tmf_id or str(o.id),
                "href": o.href,
                "name": o.name,
                "lifecycleStatus": o.lifecycle_status,
                "isBundle": False,
                "@type": "ProductOffering",
                
                # TMF Price Structure (Simplified)
                "productOfferingPrice": [{
                    "priceType": "recurring" if o.type == 'service' else "one_time",
                    "price": {
                        "value": o.list_price,
                        "unit": request.env.company.currency_id.name
                    }
                }]
            }

            # Link to the Technical Specification
            if o.product_specification_id:
                offering_json["productSpecification"] = {
                    "id": o.product_specification_id.tmf_id,
                    "href": o.product_specification_id.href,
                    "name": o.product_specification_id.name
                }

            response_data.append(offering_json)

        return request.make_response(
            json.dumps(response_data),
            headers=[('Content-Type', 'application/json')]
        )