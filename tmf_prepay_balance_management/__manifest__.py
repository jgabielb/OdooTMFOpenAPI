# tmf_prepay_balance_management/__manifest__.py
{
  "name": "TMF654 Prepay Balance Management",
  "version": "1.0.0",
  "category": "TMF",
  "depends": [
      "tmf_base",
      "tmf_product_inventory",
      "tmf_account",
      "tmf_party",
      "tmf_payment",
      # add "tmf_channel" if you have it; otherwise keep channel as JSON/text
  ],
  "data": [
      "security/ir.model.access.csv",
    #   "views/generated_views.xml",
  ],
  "installable": True,
  "application": False,
}
