import logging
import uuid
from datetime import datetime
import requests
import re
import traceback
import time
from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Regex for parsing query filters (e.g., eventType=ProductOrderCreateEvent)
_RE_EQ = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$")
_RE_IN = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s+in\s*\((.+?)\)\s*$", re.IGNORECASE)

# =========================================================
# TMF Event Name Mapping
# Keys match the 'api_name' passed from your models.
# =========================================================
TMF_EVENT_NAME_MAP = {

    # TMF632 - Party
    'party': {
        'create': 'PartyCreateEvent',
        'update': 'PartyAttributeValueChangeEvent',
        'delete': 'PartyDeleteEvent',
    },
    'individual': {
        'create': 'IndividualCreateEvent',
        'update': 'IndividualAttributeValueChangeEvent',
        'state_change': 'IndividualStateChangeEvent',
        'delete': 'IndividualDeleteEvent',
    },
    'organization': {
        'create': 'OrganizationCreateEvent',
        'update': 'OrganizationAttributeValueChangeEvent',
        'state_change': 'OrganizationStateChangeEvent',
        'delete': 'OrganizationDeleteEvent',
    },

    # TMF703 - Entity Inventory
    'entity': {
        'create': 'EntityCreateEvent',
        'update': 'EntityChangeEvent',
        'delete': 'EntityDeleteEvent',
    },
    'association': {
        'create': 'AssociationCreateEvent',
        'update': 'AssociationChangeEvent',
        'delete': 'AssociationDeleteEvent',
    },

    # TMF704 - Test Case Management
    'testCase': {
        'create': 'TestCaseCreateEvent',
        'update': 'TestCaseChangeEvent',
        'state_change': 'TestCaseStateChangeEvent',
        'delete': 'TestCaseDeleteEvent',
    },
    'testSuite': {
        'create': 'TestSuiteCreateEvent',
        'update': 'TestSuiteChangeEvent',
        'state_change': 'TestSuiteStateChangeEvent',
        'delete': 'TestSuiteDeleteEvent',
    },
    'nonFunctionalTestModel': {
        'create': 'NonFunctionalTestModelCreateEvent',
        'update': 'NonFunctionalTestModelChangeEvent',
        'state_change': 'NonFunctionalTestModelStateChangeEvent',
        'delete': 'NonFunctionalTestModelDeleteEvent',
    },

    # TMF705 - Test Environment Management
    'abstractEnvironment': {
        'create': 'AbstractEnvironmentCreateEvent',
        'update': 'AbstractEnvironmentChangeEvent',
        'state_change': 'AbstractEnvironmentStateChangeEvent',
        'delete': 'AbstractEnvironmentDeleteEvent',
    },
    'concreteEnvironmentMetaModel': {
        'create': 'ConcreteEnvironmentMetaModelCreateEvent',
        'update': 'ConcreteEnvironmentMetaModelChangeEvent',
        'state_change': 'ConcreteEnvironmentMetaModelStateChangeEvent',
        'delete': 'ConcreteEnvironmentMetaModelDeleteEvent',
    },
    'testResourceAPI': {
        'create': 'TestResourceAPICreateEvent',
        'update': 'TestResourceAPIChangeEvent',
        'state_change': 'TestResourceAPIStateChangeEvent',
        'delete': 'TestResourceAPIDeleteEvent',
    },
    'provisioningArtifact': {
        'create': 'ProvisioningArtifactCreateEvent',
        'update': 'ProvisioningArtifactChangeEvent',
        'state_change': 'ProvisioningArtifactStateChangeEvent',
        'delete': 'ProvisioningArtifactDeleteEvent',
    },

    # TMF706 - Test Data Management
    'testDataInstance': {
        'create': 'TestDataInstanceCreateEvent',
        'update': 'TestDataInstanceChangeEvent',
        'state_change': 'TestDataInstanceStateChangeEvent',
        'delete': 'TestDataInstanceDeleteEvent',
    },
    'testDataSchema': {
        'create': 'TestDataSchemaCreateEvent',
        'update': 'TestDataSchemaChangeEvent',
        'state_change': 'TestDataSchemaStateChangeEvent',
        'delete': 'TestDataSchemaDeleteEvent',
    },

    # TMF707 - Test Result Management
    'testCaseResult': {
        'create': 'TestCaseResultCreateEvent',
        'update': 'TestCaseResultChangeEvent',
        'delete': 'TestCaseResultDeleteEvent',
    },
    'testSuiteResult': {
        'create': 'TestSuiteResultCreateEvent',
        'update': 'TestSuiteResultChangeEvent',
        'delete': 'TestSuiteResultDeleteEvent',
    },
    'nonFunctionalTestResult': {
        'create': 'NonFunctionalTestResultCreateEvent',
        'update': 'NonFunctionalTestResultChangeEvent',
        'delete': 'NonFunctionalTestResultDeleteEvent',
    },

    # TMF708 - Test Execution Management
    'testEnvironmentProvisioningExecution': {
        'create': 'TestEnvironmentProvisioningExecutionCreateEvent',
        'update': 'TestEnvironmentProvisioningExecutionChangeEvent',
        'state_change': 'TestEnvironmentProvisioningExecutionStateChangeEvent',
        'delete': 'TestEnvironmentProvisioningExecutionDeleteEvent',
    },
    'testEnvironmentAllocationExecution': {
        'create': 'TestEnvironmentAllocationExecutionCreateEvent',
        'update': 'TestEnvironmentAllocationExecutionChangeEvent',
        'state_change': 'TestEnvironmentAllocationExecutionStateChangeEvent',
        'delete': 'TestEnvironmentAllocationExecutionDeleteEvent',
    },
    'testSuiteExecution': {
        'create': 'TestSuiteExecutionCreateEvent',
        'update': 'TestSuiteExecutionChangeEvent',
        'state_change': 'TestSuiteExecutionStateChangeEvent',
        'delete': 'TestSuiteExecutionDeleteEvent',
    },
    'testCaseExecution': {
        'create': 'TestCaseExecutionCreateEvent',
        'update': 'TestCaseExecutionChangeEvent',
        'state_change': 'TestCaseExecutionStateChangeEvent',
        'delete': 'TestCaseExecutionDeleteEvent',
    },
    'nonFunctionalTestExecution': {
        'create': 'NonFunctionalTestExecutionCreateEvent',
        'update': 'NonFunctionalTestExecutionChangeEvent',
        'state_change': 'NonFunctionalTestExecutionStateChangeEvent',
        'delete': 'NonFunctionalTestExecutionDeleteEvent',
    },

    # TMF709 - Test Scenario Management
    'testScenario': {
        'create': 'TestScenarioCreateEvent',
        'update': 'TestScenarioAttributeValueChangeEvent',
        'state_change': 'TestScenarioStateChangeEvent',
        'delete': 'TestScenarioDeleteEvent',
    },

    # TMF710 - General Test Artifact Management
    'generalTestArtifact': {
        'create': 'GeneralTestArtifactCreateEvent',
        'update': 'GeneralTestArtifactAttributeValueChangeEvent',
        'state_change': 'GeneralTestArtifactStateChangeEvent',
        'delete': 'GeneralTestArtifactDeleteEvent',
    },

    # TMF711 - Shipment Management
    'shipment': {
        'create': 'ShipmentCreateEvent',
        'update': 'ShipmentAttributeValueChangeEvent',
        'state_change': 'ShipmentStateChangeEvent',
        'delete': 'ShipmentDeleteEvent',
    },
    'shipmentSpecification': {
        'create': 'ShipmentSpecificationCreateEvent',
        'update': 'ShipmentSpecificationAttributeValueChangeEvent',
        'state_change': 'ShipmentSpecificationStateChangeEvent',
        'delete': 'ShipmentSpecificationDeleteEvent',
    },

    # TMF713 - Work Management
    'work': {
        'create': 'WorkCreateEvent',
        'update': 'WorkAttributeValueChangeEvent',
        'state_change': 'WorkStateChangeEvent',
        'delete': 'WorkDeleteEvent',
    },
    'workSpecification': {
        'create': 'WorkSpecificationCreateEvent',
        'update': 'WorkSpecificationAttributeValueChangeEvent',
        'state_change': 'WorkSpecificationStateChangeEvent',
        'delete': 'WorkSpecificationDeleteEvent',
    },

    # TMF714 - Work Qualification Management
    'checkWorkQualification': {
        'create': 'CheckWorkQualificationCreateEvent',
        'update': 'CheckWorkQualificationAttributeValueChangeEvent',
        'state_change': 'CheckWorkQualificationStateChangeEvent',
        'delete': 'CheckWorkQualificationDeleteEvent',
        'information_required': 'CheckWorkQualificationInformationRequiredEvent',
    },
    'queryWorkQualification': {
        'create': 'QueryWorkQualificationCreateEvent',
        'state_change': 'QueryWorkQualificationStateChangeEvent',
        'delete': 'QueryWorkQualificationDeleteEvent',
    },

    # TMF715 - Warranty Management
    'warranty': {
        'create': 'WarrantyCreateEvent',
        'update': 'WarrantyAttributeValueChangeEvent',
        'state_change': 'WarrantyStateChangeEvent',
        'delete': 'WarrantyDeleteEvent',
    },
    'warrantySpecification': {
        'create': 'WarrantySpecificationCreateEvent',
        'update': 'WarrantySpecificationAttributeValueChangeEvent',
        'state_change': 'WarrantySpecificationStateChangeEvent',
        'delete': 'WarrantySpecificationDeleteEvent',
    },

    # TMF716 - Resource Reservation
    'resourceReservation': {
        'create': 'ResourceReservationCreateEvent',
        'update': 'ResourceReservationAttributeValueChangeEvent',
        'state_change': 'ResourceReservationStateChangeEvent',
        'delete': 'ResourceReservationDeleteEvent',
        'information_required': 'ResourceReservationInformationRequiredEvent',
    },
    'cancelResourceReservation': {
        'create': 'CancelResourceReservationCreateEvent',
        'state_change': 'CancelResourceReservationStateChangeEvent',
        'information_required': 'CancelResourceReservationInformationRequiredEvent',
    },

    # TMF720 - Digital Identity Management
    'digitalIdentity': {
        'create': 'DigitalIdentityCreateEvent',
        'update': 'DigitalIdentityAttributeValueChangeEvent',
        'state_change': 'DigitalIdentityStateChangeEvent',
        'delete': 'DigitalIdentityDeleteEvent',
    },

    # TMF724 - Incident Management
    'incident': {
        'create': 'IncidentCreateEvent',
        'update': 'IncidentAttributeValueChangeEvent',
        'state_change': 'IncidentStateChangeEvent',
        'delete': 'IncidentDeleteEvent',
    },
    'diagnoseIncident': {
        'create': 'DiagnoseIncidentCreateEvent',
        'update': 'DiagnoseIncidentAttributeValueChangeEvent',
        'state_change': 'DiagnoseIncidentStateChangeEvent',
        'delete': 'DiagnoseIncidentDeleteEvent',
    },
    'resolveIncident': {
        'create': 'ResolveIncidentCreateEvent',
        'update': 'ResolveIncidentAttributeValueChangeEvent',
        'state_change': 'ResolveIncidentStateChangeEvent',
        'delete': 'ResolveIncidentDeleteEvent',
    },

    # TMF725 - Metadata Catalog Management
    'metadataCatalog': {
        'create': 'MetadataCatalogCreateEvent',
        'update': 'MetadataCatalogAttributeValueChangeEvent',
        'state_change': 'MetadataCatalogStatusChangeEvent',
        'delete': 'MetadataCatalogDeleteEvent',
    },
    'metadataCategory': {
        'create': 'MetadataCategoryCreateEvent',
        'update': 'MetadataCategoryAttributeValueChangeEvent',
        'state_change': 'MetadataCategoryStatusChangeEvent',
        'delete': 'MetadataCategoryDeleteEvent',
    },
    'metadataCatalogItem': {
        'create': 'MetadataCatalogItemCreateEvent',
        'update': 'MetadataCatalogItemAttributeValueChangeEvent',
        'state_change': 'MetadataCatalogItemStatusChangeEvent',
        'delete': 'MetadataCatalogItemDeleteEvent',
    },
    'metadataSpecification': {
        'create': 'MetadataSpecificationCreateEvent',
        'update': 'MetadataSpecificationAttributeValueChangeEvent',
        'state_change': 'MetadataSpecificationStatusChangeEvent',
        'delete': 'MetadataSpecificationDeleteEvent',
    },

    # TMF727 - Service Usage Management
    'serviceUsage': {
        'create': 'ServiceUsageCreateEvent',
        'state_change': 'ServiceUsageStatusChangeEvent',
        'delete': 'ServiceUsageDeleteEvent',
    },

    # TMF728 - Dunning Case Management
    'dunningScenario': {
        'create': 'DunningScenarioCreateEvent',
        'update': 'DunningScenarioAttributeValueChangeEvent',
        'delete': 'DunningScenarioDeleteEvent',
    },
    'dunningRule': {
        'create': 'DunningRuleCreateEvent',
        'update': 'DunningRuleAttributeValueChangeEvent',
        'delete': 'DunningRuleDeleteEvent',
    },
    'dunningCase': {
        'create': 'DunningCaseCreateEvent',
        'update': 'DunningCaseAttributeValueChangeEvent',
        'state_change': 'DunningCaseStateChangeEvent',
        'delete': 'DunningCaseDeleteEvent',
    },

    # TMF730 - Software and Compute Management
    'softwareComputeResource': {
        'create': 'ResourceCreateEvent',
        'update': 'ResourceAttributeValueChangeEvent',
        'state_change': 'ResourceStateChangeEvent',
        'delete': 'ResourceDeleteEvent',
    },
    'softwareComputeResourceSpecification': {
        'create': 'ResourceSpecificationCreateEvent',
        'update': 'ResourceSpecificationChangeEvent',
        'delete': 'ResourceSpecificationDeleteEvent',
    },

    # TMF735 - CDR Transaction Management
    'cdrTransaction': {
        'create': 'CdrTransactionCreateEvent',
        'update': 'CdrTransactionAttributeValueChangeEvent',
        'state_change': 'CdrTransactionStateChangeEvent',
        'delete': 'CdrTransactionDeleteEvent',
    },
    # TMF736 - Revenue Sharing Algorithm Management
    'partyRevSharingAlgorithm': {
        'create': 'PartyRevSharingAlgorithmCreateEvent',
        'update': 'PartyRevSharingAlgorithmAttributeValueChangeEvent',
        'state_change': 'PartyRevSharingAlgorithmStateChangeEvent',
        'delete': 'PartyRevSharingAlgorithmDeleteEvent',
    },
    # TMF737 - Revenue Sharing Report Management
    'partyRevSharingReport': {
        'create': 'PartyRevSharingReportCreateEvent',
        'update': 'PartyRevSharingReportAttributeValueChangeEvent',
        'state_change': 'PartyRevSharingReportStateChangeEvent',
        'delete': 'PartyRevSharingReportDeleteEvent',
    },
    # TMF738 - Revenue Sharing Model Management
    'partyRevSharingModel': {
        'create': 'PartyRevSharingModelCreateEvent',
        'update': 'PartyRevSharingModelAttributeValueChangeEvent',
        'state_change': 'PartyRevSharingModelStateChangeEvent',
        'delete': 'PartyRevSharingModelDeleteEvent',
    },
    # TMF759 - Private Optimized Binding
    'cloudApplication': {
        'create': 'CloudApplicationCreateEvent',
        'update': 'CloudApplicationAttributeValueChangeEvent',
        'state_change': 'CloudApplicationStateChangeEvent',
        'delete': 'CloudApplicationDeleteEvent',
    },
    'cloudApplicationSpecification': {
        'create': 'CloudApplicationSpecificationCreateEvent',
        'update': 'CloudApplicationSpecificationAttributeValueChangeEvent',
        'delete': 'CloudApplicationSpecificationDeleteEvent',
    },
    'userEquipment': {
        'create': 'UserEquipmentCreateEvent',
        'update': 'UserEquipmentAttributeValueChangeEvent',
        'state_change': 'UserEquipmentStateChangeEvent',
        'delete': 'UserEquipmentDeleteEvent',
    },
    'userEquipmentSpecification': {
        'create': 'UserEquipmentSpecificationCreateEvent',
        'update': 'UserEquipmentSpecificationAttributeValueChangeEvent',
        'delete': 'UserEquipmentSpecificationDeleteEvent',
    },
    # TMF908 - IoT Agent and Device Management
    'iotDevice': {
        'create': 'IotDeviceCreateEvent',
        'update': 'IotDeviceChangeEvent',
        'state_change': 'IotDeviceStateChangeEvent',
        'delete': 'IotDeviceDeleteEvent',
    },
    'dataAccessEndpoint': {
        'create': 'DataAccessEndpointCreateEvent',
        'update': 'DataAccessEndpointChangeEvent',
        'delete': 'DataAccessEndpointDeleteEvent',
    },
    'iotDeviceSpecification': {
        'create': 'IotDeviceSpecificationCreateEvent',
        'update': 'IotDeviceSpecificationChangeEvent',
        'delete': 'IotDeviceSpecificationDeleteEvent',
    },
    'iotDataEvent': {
        'create': 'IotDataEventCreateEvent',
        'update': 'IotDataEventChangeEvent',
        'delete': 'IotDataEventDeleteEvent',
    },
    'iotManagementEvent': {
        'create': 'IotManagementEventCreateEvent',
        'update': 'IotManagementEventChangeEvent',
        'delete': 'IotManagementEventDeleteEvent',
    },

    # TMF915 - AI Management
    'aiModel': {
        'create': 'AiModelCreateEvent',
        'update': 'AiModelAttributeValueChangeEvent',
        'state_change': 'AiModelStateChangeEvent',
        'delete': 'AiModelDeleteEvent',
    },
    'aiModelSpecification': {
        'create': 'AiModelSpecificationCreateEvent',
        'update': 'AiModelSpecificationAttributeValueChangeEvent',
        'delete': 'AiModelSpecificationDeleteEvent',
    },
    'aiContract': {
        'create': 'AiContractCreateEvent',
        'update': 'AiContractAttributeValueChangeEvent',
        'state_change': 'AiContractStateChangeEvent',
        'delete': 'AiContractDeleteEvent',
    },
    'aiContractSpecification': {
        'create': 'AiContractSpecificationCreateEvent',
        'update': 'AiContractSpecificationAttributeValueChangeEvent',
        'delete': 'AiContractSpecificationDeleteEvent',
    },
    'aiContractViolation': {
        'create': 'AiContractViolationCreateEvent',
        'update': 'AiContractViolationAttributeValueChangeEvent',
        'delete': 'AiContractViolationDeleteEvent',
    },
    'rule': {
        'create': 'RuleCreateEvent',
        'update': 'RuleAttributeValueChangeEvent',
        'state_change': 'RuleStateChangeEvent',
        'delete': 'RuleDeleteEvent',
    },

    # TMF921 - Intent Management
    'intent': {
        'create': 'IntentCreateEvent',
        'update': 'IntentAttributeValueChangeEvent',
        'state_change': 'IntentStatusChangeEvent',
        'delete': 'IntentDeleteEvent',
    },
    'intentReport': {
        'create': 'IntentReportCreateEvent',
        'update': 'IntentReportAttributeValueChangeEvent',
        'delete': 'IntentReportDeleteEvent',
    },
    'intentSpecification': {
        'create': 'IntentSpecificationCreateEvent',
        'update': 'IntentSpecificationAttributeValueChangeEvent',
        'state_change': 'IntentSpecificationStatusChangeEvent',
        'delete': 'IntentSpecificationDeleteEvent',
    },
    # TMF760 - Product Configuration Management
    'checkProductConfiguration': {
        'create': 'CheckProductConfigurationCreateEvent',
        'update': 'CheckProductConfigurationAttributeValueChangeEvent',
        'state_change': 'CheckProductConfigurationStateChangeEvent',
        'delete': 'CheckProductConfigurationDeleteEvent',
    },
    'queryProductConfiguration': {
        'create': 'QueryProductConfigurationCreateEvent',
        'update': 'QueryProductConfigurationAttributeValueChangeEvent',
        'state_change': 'QueryProductConfigurationStateChangeEvent',
        'delete': 'QueryProductConfigurationDeleteEvent',
    },

    # TMF764 - Cost Management
    'actualCost': {
        'create': 'ActualCostCreateEvent',
        'update': 'ActualCostAttributeValueChangeEvent',
        'state_change': 'ActualCostStateChangeEvent',
        'delete': 'ActualCostDeleteEvent',
    },
    'projectedCost': {
        'create': 'ProjectedCostCreateEvent',
        'update': 'ProjectedCostAttributeValueChangeEvent',
        'state_change': 'ProjectedCostStateChangeEvent',
        'delete': 'ProjectedCostDeleteEvent',
    },

    # TMF767 - Product Usage Catalog Management
    'productUsageSpecification': {
        'create': 'ProductUsageSpecificationCreateEvent',
        'update': 'ProductUsageSpecificationAttributeValueChangeEvent',
        'state_change': 'ProductUsageSpecificationStateChangeEvent',
        'delete': 'ProductUsageSpecificationDeleteEvent',
    },

    # TMF768 - Resource Role Management
    'resourceRole': {
        'create': 'ResourceRoleCreateEvent',
        'update': 'ResourceRoleAttributeValueChangeEvent',
        'state_change': 'ResourceRoleStatusChangeEvent',
        'delete': 'ResourceRoleDeleteEvent',
    },
    'resourceRoleSpecification': {
        'create': 'ResourceRoleSpecificationCreateEvent',
        'update': 'ResourceRoleSpecificationAttributeValueChangeEvent',
        'state_change': 'ResourceRoleSpecificationStatusChangeEvent',
        'delete': 'ResourceRoleSpecificationDeleteEvent',
    },
    # TMF771 - Resource Usage Management
    'resourceUsage': {
        'create': 'ResourceUsageCreateEvent',
        'update': 'ResourceUsageAttributeValueChangeEvent',
        'delete': 'ResourceUsageDeleteEvent',
    },
    'resourceUsageSpecification': {
        'create': 'ResourceUsageSpecificationCreateEvent',
        'update': 'ResourceUsageSpecificationAttributeValueChangeEvent',
        'delete': 'ResourceUsageSpecificationDeleteEvent',
    },

    # TMF777 - Outage Management
    'outage': {
        'create': 'OutageCreateEvent',
        'update': 'OutageAttributeValueChangeEvent',
        'state_change': 'OutageStateChangeEvent',
        'delete': 'OutageDeleteEvent',
    },
    # TMF931 - Open Gateway Operate API - Onboarding and Ordering
    'apiProductOrder': {
        'create': 'ApiProductOrderCreateEvent',
        'update': 'ApiProductOrderAttributeValueChangeEvent',
        'state_change': 'ApiProductOrderStateChangeEvent',
    },
    'application': {
        'create': 'ApplicationCreateEvent',
        'update': 'ApplicationAttributeValueChangeEvent',
        'state_change': 'ApplicationApprovalStatusChangeEvent',
    },
    'applicationOwner': {
        'create': 'ApplicationOwnerCreateEvent',
        'update': 'ApplicationOwnerAttributeValueChangeEvent',
        'state_change': 'ApplicationOwnerApprovalStatusChangeEvent',
    },
    'monitor': {
        'state_change': 'MonitorStateChangeEvent',
    },

    # TMF936 - Open Gateway Operate API - Product Catalog
    'productOffering': {
        'create': 'ProductOfferingCreateEvent',
        'update': 'ProductOfferingAttributeValueChangeEvent',
        'state_change': 'ProductOfferingStateChangeEvent',
        'delete': 'ProductOfferingDeleteEvent',
    },
    # TMF629 - Customer
    'customer': {
        'create': 'CustomerCreateEvent',
        'update': 'CustomerAttributeValueChangeEvent',
        'delete': 'CustomerDeleteEvent',
    },

    # TMF648 - Quote Management
    'quote': {
        'create': 'QuoteCreateEvent',
        'update': 'QuoteAttributeValueChangeEvent',
        'state_change': 'QuoteStateChangeEvent',
        'information_required': 'QuoteInformationRequiredEvent',
        'delete': 'QuoteDeleteEvent',
    },

    # TMF676 - Payment Management
    'payment': {
        'create': 'PaymentCreateEvent',
        'update': 'PaymentAttributeValueChangeEvent',
        'delete': 'PaymentDeleteEvent',
    },

    # TMF622 - Product Ordering (resource: productOrder)
    'productOrder': {
        'create': 'ProductOrderCreateEvent',
        'update': 'ProductOrderAttributeValueChangeEvent',
        'state_change': 'ProductOrderStateChangeEvent',
        'information_required': 'ProductOrderInformationRequiredEvent',
        'delete': 'ProductOrderDeleteEvent',
    },

    # TMF641 - Service Ordering
    'serviceOrder': {
        'create': 'ServiceOrderCreateEvent',
        'update': 'ServiceOrderAttributeValueChangeEvent',
        'state_change': 'ServiceOrderStateChangeEvent',
        'delete': 'ServiceOrderDeleteEvent',
    },

    # TMF652 - Resource Ordering
    'resourceOrder': {
        'create': 'ResourceOrderCreateEvent',
        'update': 'ResourceOrderAttributeValueChangeEvent',
        'state_change': 'ResourceOrderStateChangeEvent',
        'delete': 'ResourceOrderDeleteEvent',
    },

    # TMF620 - Product Catalog
    # Usa fallback si no distingues offering/specification
    'productCatalog': {
        'create': 'ProductOfferingCreateEvent',
        'update': 'ProductOfferingAttributeValueChangeEvent',
        'delete': 'ProductOfferingDeleteEvent',
    },

    # Opcional: separación fina TMF620
    'productOffering': {
        'create': 'ProductOfferingCreateEvent',
        'update': 'ProductOfferingAttributeValueChangeEvent',
        'state_change': 'ProductOfferingStateChangeEvent',
        'delete': 'ProductOfferingDeleteEvent',
    },
    'productSpecification': {
        'create': 'ProductSpecificationCreateEvent',
        'update': 'ProductSpecificationAttributeValueChangeEvent',
        'state_change': 'ProductSpecificationStateChangeEvent',
        'delete': 'ProductSpecificationDeleteEvent',
    },
    'productOfferingPrice': {
        'create': 'ProductOfferingPriceCreateEvent',
        'update': 'ProductOfferingPriceAttributeValueChangeEvent',
        'state_change': 'ProductOfferingPriceStateChangeEvent',
        'delete': 'ProductOfferingPriceDeleteEvent',
    },

    # TMF638 - Service Inventory (resource: service)
    'service': {
        'create': 'ServiceCreateEvent',
        'update': 'ServiceAttributeValueChangeEvent',
        'state_change': 'ServiceStateChangeEvent',
        'delete': 'ServiceDeleteEvent',
    },

    # TMF668 - Partnership Management
    'partnership': {
        'create': 'PartnershipCreateEvent',
        'update': 'PartnershipAttributeValueChangeEvent',
        'delete': 'PartnershipDeleteEvent',
    },
    'partnershipSpecification': {
        'create': 'PartnershipSpecificationCreateEvent',
        'update': 'PartnershipSpecificationAttributeValueChangeEvent',
        'delete': 'PartnershipSpecificationDeleteEvent',
    },

    # TMF639 - Resource Inventory (resource: resource)
    'resource': {
        'create': 'ResourceCreateEvent',
        'update': 'ResourceAttributeValueChangeEvent',
        'state_change': 'ResourceStateChangeEvent',
        'delete': 'ResourceDeleteEvent',
    },
    # TMF664 - Resource Function Activation
    'resourceFunction': {
        'create': 'ResourceFunctionCreateEvent',
        'update': 'ResourceFunctionAttributeValueChangeEvent',
        'state_change': 'ResourceFunctionStateChangeEvent',
        'delete': 'ResourceFunctionDeleteEvent',
    },
    'monitor': {
        'create': 'MonitorCreateEvent',
        'update': 'MonitorAttributeValueChangeEvent',
        'state_change': 'MonitorStateChangeEvent',
        'delete': 'MonitorDeleteEvent',
    },

    # TMF621 - Trouble Ticket (resource: troubleTicket)
    'troubleTicket': {
        'create': 'TroubleTicketCreateEvent',
        'update': 'TroubleTicketAttributeValueChangeEvent',
        # TMF621 define cambio de estado como StatusChange (no StateChange)
        'state_change': 'TroubleTicketStatusChangeEvent',
        'delete': 'TroubleTicketDeleteEvent',
    },

    # TMF666 - Account Management
    'account': {
        'create': 'AccountCreateEvent',
        'update': 'AccountAttributeValueChangeEvent',
        'state_change': 'AccountStateChangeEvent',
        'delete': 'AccountDeleteEvent',
    },

    # TMF651 - Agreement Management
    'agreement': {
        'create': 'AgreementCreateEvent',
        'update': 'AgreementAttributeValueChangeEvent',
        'state_change': 'AgreementStateChangeEvent',
        'delete': 'AgreementDeleteEvent',
    },
    'agreementSpecification': {
        'create': 'AgreementSpecificationCreateEvent',
        'update': 'AgreementSpecificationAttributeValueChangeEvent',
        'state_change': 'AgreementSpecificationStateChangeEvent',
        'delete': 'AgreementSpecificationDeleteEvent',
    },

    # TMF670 - Payment Method Management
    'paymentMethod': {
        'create': 'PaymentMethodCreateEvent',
        'update': 'PaymentMethodAttributeValueChangeEvent',
        'delete': 'PaymentMethodDeleteEvent',
    },

    # TMF678 - Customer Bill Management
    'customerBill': {
        'create': 'CustomerBillCreateEvent',
        'update': 'CustomerBillAttributeValueChangeEvent',
        'state_change': 'CustomerBillStateChangeEvent',
        'delete': 'CustomerBillDeleteEvent',
    },

    # TMF688 - Event Management
    'event': {
        'create': 'EventCreateEvent',
        'update': 'EventChangeEvent',
        'delete': 'EventDeleteEvent',
    },
    'topic': {
        'create': 'TopicCreateEvent',
        'update': 'TopicChangeEvent',
        'delete': 'TopicDeleteEvent',
    },

    # TMF696 - Risk Management
    'productOfferingRiskAssessment': {
        'create': 'ProductOfferingRiskAssessmentCreateEvent',
        'state_change': 'ProductOfferingRiskAssessmentStatusChangeEvent',
        'delete': 'ProductOfferingRiskAssessmentDeleteEvent',
    },
    'partyRoleRiskAssessment': {
        'create': 'PartyRoleRiskAssessmentCreateEvent',
        'state_change': 'PartyRoleRiskAssessmentStatusChangeEvent',
        'delete': 'PartyRoleRiskAssessmentDeleteEvent',
    },
    'partyRoleProductOfferingRiskAssessment': {
        'create': 'PartyRoleProductOfferingRiskAssessmentCreateEvent',
        'state_change': 'PartyRoleProductOfferingRiskAssessmentStatusChangeEvent',
        'delete': 'PartyRoleProductOfferingRiskAssessmentDeleteEvent',
    },
    'shoppingCartRiskAssessment': {
        'create': 'ShoppingCartRiskAssessmentCreateEvent',
        'state_change': 'ShoppingCartRiskAssessmentStatusChangeEvent',
        'delete': 'ShoppingCartRiskAssessmentDeleteEvent',
    },
    'productOrderRiskAssessment': {
        'create': 'ProductOrderRiskAssessmentCreateEvent',
        'state_change': 'ProductOrderRiskAssessmentStatusChangeEvent',
        'delete': 'ProductOrderRiskAssessmentDeleteEvent',
    },

    # TMF699 - Sales Management
    'salesLead': {
        'create': 'SalesLeadCreateEvent',
        'update': 'SalesLeadAttributeValueChangeEvent',
        'state_change': 'SalesLeadStateChangeEvent',
        'delete': 'SalesLeadDeleteEvent',
    },

    # TMF655 - Change Management
    'changeRequest': {
        'create': 'ChangeRequestCreateEvent',
        'update': 'ChangeRequestAttributeValueChangeEvent',
        'delete': 'ChangeRequestDeleteEvent',
    },

    # TMF717 - Customer360
    'customer360': {
        'create': 'Customer360CreateEvent',
        'update': 'Customer360AttributeValueChangeEvent',
        'delete': 'Customer360DeleteEvent',
    },

    # TMF673 - Geographic Address
    'geographicAddress': {
        'create': 'GeographicAddressCreateEvent',
        'update': 'GeographicAddressAttributeValueChangeEvent',
        'delete': 'GeographicAddressDeleteEvent',
    },
    'geographicAddressValidation': {
        'create': 'GeographicAddressValidationCreateEvent',
        'update': 'GeographicAddressValidationAttributeValueChangeEvent',
        'delete': 'GeographicAddressValidationDeleteEvent',
    },

    # TMF683 - Party Interaction
    'partyInteraction': {
        'create': 'PartyInteractionCreateEvent',
        'update': 'PartyInteractionAttributeValueChangeEvent',
        'delete': 'PartyInteractionDeleteEvent',
    },

    # TMF671 - Promotion Management
    'promotion': {
        'create': 'PromotionCreateEvent',
        'update': 'PromotionAttributeValueChangeEvent',
        'delete': 'PromotionDeleteEvent',
    },

    # TMF700 - Shipping Order Management
    'shippingOrder': {
        'create': 'ShippingOrderCreateEvent',
        'update': 'ShippingOrderAttributeValueChangeEvent',
        'state_change': 'ShippingOrderStateChangeEvent',
        'delete': 'ShippingOrderDeleteEvent',
        'information_required': 'ShippingOrderInformationRequiredEvent',
    },

    # TMF684 - Shipment Tracking Management
    'shipmentTracking': {
        'create': 'ShipmentTrackingCreateEvent',
        'update': 'ShipmentTrackingAttributeValueChangeEvent',
        'state_change': 'ShipmentTrackingStateChangeEvent',
        'delete': 'ShipmentTrackingDeleteEvent',
    },

    # TMF654 - Prepay Balance Management
    'bucket': {
        'create': 'BucketCreateEvent',
        'update': 'BucketAttributeValueChangeEvent',
        'delete': 'BucketDeleteEvent',
    },

    # TMF701 - Process Flow Management
    'processFlowSpecification': {
        'create': 'ProcessFlowSpecificationCreateEvent',
        'update': 'ProcessFlowSpecificationAttributeValueChangeEvent',
        'state_change': 'ProcessFlowSpecificationStateChangeEvent',
        'delete': 'ProcessFlowSpecificationDeleteEvent',
    },
    'taskFlowSpecification': {
        'create': 'TaskFlowSpecificationCreateEvent',
        'update': 'TaskFlowSpecificationAttributeValueChangeEvent',
        'state_change': 'TaskFlowSpecificationStateChangeEvent',
        'delete': 'TaskFlowSpecificationDeleteEvent',
    },
    'processFlow': {
        'create': 'ProcessFlowCreateEvent',
        'update': 'ProcessFlowAttributeValueChangeEvent',
        'state_change': 'ProcessFlowStateChangeEvent',
        'delete': 'ProcessFlowDeleteEvent',
    },
    'taskFlow': {
        'create': 'TaskFlowCreateEvent',
        'update': 'TaskFlowAttributeValueChangeEvent',
        'state_change': 'TaskFlowStateChangeEvent',
        'delete': 'TaskFlowDeleteEvent',
        'information_required': 'TaskFlowInformationRequiredEvent',
    },

    # TMF687 - Product Stock Relationship
    'productStock': {
        'create': 'ProductStockCreateEvent',
        'update': 'ProductStockAttributeValueChangeEvent',
        'delete': 'ProductStockDeleteEvent',
    },
    'reserveProductStock': {
        'create': 'ReserveProductStockCreateEvent',
        'update': 'ReserveProductStockAttributeValueChangeEvent',
        'delete': 'ReserveProductStockDeleteEvent',
    },

    # TMF685 - Resource Pool Management
    'resourcePool': {
        'create': 'ResourcePoolCreateEvent',
        'update': 'ResourcePoolAttributeValueChangeEvent',
        'delete': 'ResourcePoolDeleteEvent',
    },

    # TMF645 - Service Qualification
    'serviceQualification': {
        'create': 'ServiceQualificationCreateEvent',
        'update': 'ServiceQualificationAttributeValueChangeEvent',
        'delete': 'ServiceQualificationDeleteEvent',
    },

    # TMF656 - Service Problem
    'serviceProblem': {
        'create': 'ServiceProblemCreateEvent',
        'update': 'ServiceProblemAttributeValueChangeEvent',
        'delete': 'ServiceProblemDeleteEvent',
    },
    'problemAcknowledgement': {
        'create': 'ProblemAcknowledgementCreateEvent',
        'update': 'ProblemAcknowledgementAttributeValueChangeEvent',
        'delete': 'ProblemAcknowledgementDeleteEvent',
    },
    'problemUnacknowledgement': {
        'create': 'ProblemUnacknowledgementCreateEvent',
        'update': 'ProblemUnacknowledgementAttributeValueChangeEvent',
        'delete': 'ProblemUnacknowledgementDeleteEvent',
    },
    'problemGroup': {
        'create': 'ProblemGroupCreateEvent',
        'update': 'ProblemGroupAttributeValueChangeEvent',
        'delete': 'ProblemGroupDeleteEvent',
    },
    'problemUngroup': {
        'create': 'ProblemUngroupCreateEvent',
        'update': 'ProblemUngroupAttributeValueChangeEvent',
        'delete': 'ProblemUngroupDeleteEvent',
    },

    # TMF680 - Recommendation Management
    'queryProductRecommendation': {
        'create': 'QueryProductRecommendationCreateEvent',
        'update': 'QueryProductRecommendationAttributeValueChangeEvent',
        'delete': 'QueryProductRecommendationDeleteEvent',
    },

    # Additional coverage for modules already emitting notifications
    'alarm': {
        'create': 'AlarmCreateEvent',
        'update': 'AlarmAttributeValueChangeEvent',
        'state_change': 'AlarmStateChangeEvent',
        'delete': 'AlarmDeleteEvent',
    },
    'appointment': {
        'create': 'AppointmentCreateEvent',
        'update': 'AppointmentAttributeValueChangeEvent',
        'state_change': 'AppointmentStateChangeEvent',
        'delete': 'AppointmentDeleteEvent',
    },
    'communicationMessage': {
        'create': 'CommunicationMessageCreateEvent',
        'update': 'CommunicationMessageAttributeValueChangeEvent',
        'state_change': 'CommunicationMessageStateChangeEvent',
        'delete': 'CommunicationMessageDeleteEvent',
    },
    'device': {
        'create': 'DeviceCreateEvent',
        'update': 'DeviceAttributeValueChangeEvent',
        'state_change': 'DeviceStateChangeEvent',
        'delete': 'DeviceDeleteEvent',
    },
    'document': {
        'create': 'DocumentCreateEvent',
        'update': 'DocumentAttributeValueChangeEvent',
        'state_change': 'DocumentStateChangeEvent',
        'delete': 'DocumentDeleteEvent',
    },
    'entityCatalog': {
        'create': 'EntityCatalogCreateEvent',
        'update': 'EntityCatalogAttributeValueChangeEvent',
        'state_change': 'EntityCatalogStateChangeEvent',
        'delete': 'EntityCatalogDeleteEvent',
    },
    'geographicLocation': {
        'create': 'GeographicLocationCreateEvent',
        'update': 'GeographicLocationAttributeValueChangeEvent',
        'state_change': 'GeographicLocationStateChangeEvent',
        'delete': 'GeographicLocationDeleteEvent',
    },
    'geographicSite': {
        'create': 'GeographicSiteCreateEvent',
        'update': 'GeographicSiteAttributeValueChangeEvent',
        'state_change': 'GeographicSiteStateChangeEvent',
        'delete': 'GeographicSiteDeleteEvent',
    },
    'managedEntity': {
        'create': 'ManagedEntityCreateEvent',
        'update': 'ManagedEntityAttributeValueChangeEvent',
        'state_change': 'ManagedEntityStateChangeEvent',
        'delete': 'ManagedEntityDeleteEvent',
    },
    'nonFunctionalTestResultDefinition': {
        'create': 'NonFunctionalTestResultDefinitionCreateEvent',
        'update': 'NonFunctionalTestResultDefinitionAttributeValueChangeEvent',
        'state_change': 'NonFunctionalTestResultDefinitionStateChangeEvent',
        'delete': 'NonFunctionalTestResultDefinitionDeleteEvent',
    },
    'partyPrivacyAgreement': {
        'create': 'PartyPrivacyAgreementCreateEvent',
        'update': 'PartyPrivacyAgreementAttributeValueChangeEvent',
        'state_change': 'PartyPrivacyAgreementStateChangeEvent',
        'delete': 'PartyPrivacyAgreementDeleteEvent',
    },
    'partyRole': {
        'create': 'PartyRoleCreateEvent',
        'update': 'PartyRoleAttributeValueChangeEvent',
        'state_change': 'PartyRoleStateChangeEvent',
        'delete': 'PartyRoleDeleteEvent',
    },
    'permission': {
        'create': 'PermissionCreateEvent',
        'update': 'PermissionAttributeValueChangeEvent',
        'state_change': 'PermissionStateChangeEvent',
        'delete': 'PermissionDeleteEvent',
    },
    'physicalResource': {
        'create': 'PhysicalResourceCreateEvent',
        'update': 'PhysicalResourceAttributeValueChangeEvent',
        'state_change': 'PhysicalResourceStateChangeEvent',
        'delete': 'PhysicalResourceDeleteEvent',
    },
    'product': {
        'create': 'ProductCreateEvent',
        'update': 'ProductAttributeValueChangeEvent',
        'state_change': 'ProductStateChangeEvent',
        'delete': 'ProductDeleteEvent',
    },
    'checkProductOfferingQualification': {
        'create': 'CheckProductOfferingQualificationCreateEvent',
        'update': 'CheckProductOfferingQualificationAttributeValueChangeEvent',
        'state_change': 'CheckProductOfferingQualificationStateChangeEvent',
        'delete': 'CheckProductOfferingQualificationDeleteEvent',
    },
    'resourceCatalog': {
        'create': 'ResourceCatalogCreateEvent',
        'update': 'ResourceCatalogAttributeValueChangeEvent',
        'state_change': 'ResourceCatalogStateChangeEvent',
        'delete': 'ResourceCatalogDeleteEvent',
    },
    'resourceInventory': {
        'create': 'ResourceInventoryCreateEvent',
        'update': 'ResourceInventoryAttributeValueChangeEvent',
        'state_change': 'ResourceInventoryStateChangeEvent',
        'delete': 'ResourceInventoryDeleteEvent',
    },
    'serviceCatalog': {
        'create': 'ServiceCatalogCreateEvent',
        'update': 'ServiceCatalogAttributeValueChangeEvent',
        'state_change': 'ServiceCatalogStateChangeEvent',
        'delete': 'ServiceCatalogDeleteEvent',
    },
    'serviceSpecification': {
        'create': 'ServiceSpecificationCreateEvent',
        'update': 'ServiceSpecificationAttributeValueChangeEvent',
        'state_change': 'ServiceSpecificationStateChangeEvent',
        'delete': 'ServiceSpecificationDeleteEvent',
    },
    'serviceLevelObjective': {
        'create': 'ServiceLevelObjectiveCreateEvent',
        'update': 'ServiceLevelObjectiveAttributeValueChangeEvent',
        'state_change': 'ServiceLevelObjectiveStateChangeEvent',
        'delete': 'ServiceLevelObjectiveDeleteEvent',
    },
    'serviceTest': {
        'create': 'ServiceTestCreateEvent',
        'update': 'ServiceTestAttributeValueChangeEvent',
        'state_change': 'ServiceTestStateChangeEvent',
        'delete': 'ServiceTestDeleteEvent',
    },
    'serviceTestSpecification': {
        'create': 'ServiceTestSpecificationCreateEvent',
        'update': 'ServiceTestSpecificationAttributeValueChangeEvent',
        'state_change': 'ServiceTestSpecificationStateChangeEvent',
        'delete': 'ServiceTestSpecificationDeleteEvent',
    },
    'shoppingCart': {
        'create': 'ShoppingCartCreateEvent',
        'update': 'ShoppingCartAttributeValueChangeEvent',
        'state_change': 'ShoppingCartStateChangeEvent',
        'delete': 'ShoppingCartDeleteEvent',
    },
    'testDataInstanceDefinition': {
        'create': 'TestDataInstanceDefinitionCreateEvent',
        'update': 'TestDataInstanceDefinitionAttributeValueChangeEvent',
        'state_change': 'TestDataInstanceDefinitionStateChangeEvent',
        'delete': 'TestDataInstanceDefinitionDeleteEvent',
    },
    'transferBalance': {
        'create': 'TransferBalanceCreateEvent',
        'update': 'TransferBalanceAttributeValueChangeEvent',
        'state_change': 'TransferBalanceStateChangeEvent',
        'delete': 'TransferBalanceDeleteEvent',
    },
    'usageManagement': {
        'create': 'UsageManagementCreateEvent',
        'update': 'UsageManagementAttributeValueChangeEvent',
        'state_change': 'UsageManagementStateChangeEvent',
        'delete': 'UsageManagementDeleteEvent',
    },
    'queryUsageConsumption': {
        'create': 'QueryUsageConsumptionCreateEvent',
        'update': 'QueryUsageConsumptionAttributeValueChangeEvent',
        'state_change': 'QueryUsageConsumptionStateChangeEvent',
        'delete': 'QueryUsageConsumptionDeleteEvent',
    },
    'usageConsumptionReport': {
        'create': 'UsageConsumptionReportCreateEvent',
        'update': 'UsageConsumptionReportAttributeValueChangeEvent',
        'state_change': 'UsageConsumptionReportStateChangeEvent',
        'delete': 'UsageConsumptionReportDeleteEvent',
    },
    'userinfo': {
        'create': 'UserinfoCreateEvent',
        'update': 'UserinfoAttributeValueChangeEvent',
        'state_change': 'UserinfoStateChangeEvent',
        'delete': 'UserinfoDeleteEvent',
    },
    'riskAssessment': {
        'create': 'RiskAssessmentCreateEvent',
        'update': 'RiskAssessmentAttributeValueChangeEvent',
        'state_change': 'RiskAssessmentStateChangeEvent',
        'delete': 'RiskAssessmentDeleteEvent',
    },
}

def _strip_quotes(s: str) -> str:
    s = s.strip()
    if (len(s) >= 2) and ((s[0] == s[-1]) and s[0] in ("'", '"')):
        return s[1:-1].strip()
    return s

def _split_csv_list(s: str) -> list[str]:
    parts = [p.strip() for p in s.split(",")]
    return [_strip_quotes(p) for p in parts if p.strip()]

def _normalize_query(q: str) -> list[str]:
    if not q:
        return []
    q = q.strip()
    clauses = [c.strip() for c in q.split("&") if c.strip()]
    return clauses

def _query_matches_payload(query: str, payload: dict) -> bool:
    """
    Evaluates subscription queries against the event payload.
    Supports: key=value AND key in (a,b)
    """
    if not query:
        return True

    def get_value(key: str):
        # 1. Check top level (eventId, eventType)
        if key in payload:
            return payload.get(key)
        # 2. Check 'event' object
        ev = payload.get("event") or {}
        if isinstance(ev, dict) and key in ev:
            return ev.get(key)
        # 3. Check 'resource' inside event (common TMF pattern)
        res = ev.get("resource") if isinstance(ev, dict) else None
        if isinstance(res, dict) and key in res:
            return res.get(key)
        return None

    for clause in _normalize_query(query):
        # Handle IN operator
        m_in = _RE_IN.match(clause)
        if m_in:
            key = m_in.group(1)
            values = _split_csv_list(m_in.group(2))
            actual = get_value(key)
            if actual is None or str(actual) not in values:
                return False
            continue

        # Handle EQUALS operator
        m_eq = _RE_EQ.match(clause)
        if m_eq:
            key = m_eq.group(1)
            expected = _strip_quotes(m_eq.group(2))
            actual = get_value(key)
            if actual is None or str(actual) != expected:
                return False
            continue

        _logger.warning("Unsupported TMF query clause: %r", clause)
        return False

    return True


class TMFHubSubscription(models.Model):
    _name = 'tmf.hub.subscription'
    _description = 'TMF Event Hub Subscription'

    name = fields.Char(string="Name", required=True)
    api_name = fields.Char(string="API Resource Name", required=True, help="e.g. troubleTicket, productOrder, party")
    callback = fields.Char(string="Callback URL", required=True)
    query = fields.Char(string="Query Filter")
    
    # Internal Action mapping
    event_type = fields.Selection([
        ('create', 'Create'),
        ('update', 'Update'),
        ('state_change', 'State Change'),
        ('information_required', 'Information Required'),
        ('delete', 'Delete'),
        ('any', 'Any'),
    ], default='any', required=True, string="Trigger Action")
    
    content_type = fields.Selection([
        ('application/json', 'JSON'),
    ], default='application/json')
    
    secret = fields.Char(string="Secret / Token")
    active = fields.Boolean(default=True)
    last_status = fields.Char()

    def _safe_set_last_status(self, sub, status_text, retries=2):
        for attempt in range(retries + 1):
            try:
                with self.env.cr.savepoint():
                    sub.sudo().write({"last_status": status_text})
                return
            except Exception as e:
                msg = str(e).lower()
                is_serialization = (
                    getattr(e, "pgcode", None) == "40001"
                    or "could not serialize access due to concurrent update" in msg
                )
                if is_serialization and attempt < retries:
                    time.sleep(0.05 * (attempt + 1))
                    continue
                _logger.warning(
                    "TMF Hub: failed to update last_status for subscription %s: %s",
                    sub.id,
                    e,
                )
                return

    @api.model
    def _resolve_event_names(self, api_name, input_event_type):
        """
        Helper to normalize inputs.
        Input: api_name='troubleTicket', input_event_type='TroubleTicketCreateEvent'
        Output: action='create', tmf_string='TroubleTicketCreateEvent'
        """
        mapping = TMF_EVENT_NAME_MAP.get(api_name, {})
        
        # Case 1: Input is already a raw action ('create', 'update')
        if input_event_type in mapping:
            return input_event_type, mapping[input_event_type]
        
        # Case 2: Input is a TMF String ('TroubleTicketCreateEvent') -> Reverse lookup the action
        for action, tmf_string in mapping.items():
            if tmf_string == input_event_type:
                # Map specific state changes to 'update' for subscription filtering
                internal_action = 'update' if 'change' in action.lower() else action
                return internal_action, tmf_string
                
        # Case 3: Unknown / Fallback
        return 'update', input_event_type

    @api.model
    def _notify_subscribers(self, api_name, event_type, resource_json):
        """
        Main Dispatcher.
        api_name: 'troubleTicket', 'productOrder', etc.
        event_type: Can be 'create' OR 'TroubleTicketCreateEvent'
        resource_json: The TMF JSON representation of the object.
        """
        
        # 1. Resolve to Internal Action (for DB Search) and TMF String (for JSON payload)
        action, tmf_event_name = self._resolve_event_names(api_name, event_type)

        # 2. Find matching subscriptions
        domain = [
            ("active", "=", True),
            ("api_name", "=", api_name),
            "|",
                ("event_type", "=", action), # Matches 'create', 'update', 'delete'
                ("event_type", "=", "any"),
        ]
        
        subs = self.search(domain)
        if not subs:
            return

        # 3. Construct Payload
        payload = {
            "eventId": str(uuid.uuid4()),
            "eventTime": datetime.utcnow().isoformat() + "Z",
            "eventType": tmf_event_name,
            "@type": tmf_event_name,
            "event": resource_json if isinstance(resource_json, dict) else {"resource": resource_json},
        }

        # 4. Dispatch
        for sub in subs:
            # Apply Query Filter (e.g. status=Resolved)
            if sub.query and not _query_matches_payload(sub.query, payload):
                continue

            headers = {"Content-Type": sub.content_type or "application/json"}
            if sub.secret:
                headers["X-Hub-Signature"] = sub.secret

            try:
                resp = requests.post(sub.callback, json=payload, headers=headers, timeout=5)
                self._safe_set_last_status(sub, f"{resp.status_code} {resp.reason}")
            except Exception as e:
                _logger.error(f"TMF Hub Error ({sub.callback}): {e}")
                self._safe_set_last_status(sub, f"Error: {str(e)}")




