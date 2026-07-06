# CPRA Non-Response Escalation Letter

**To:** {{agency_name}} — City/County Attorney and Public Records Coordinator
**From:** {{requester_name}} <{{requester_email}}>
**Date:** {{date}}
**Re:** FAILURE TO RESPOND — Public Records Act Request dated {{original_request_date}}

Dear Counsel:

On {{original_request_date}}, I submitted a California Public Records Act request to {{agency_name}} seeking records of enforcement actions concerning unhoused persons (copy attached). As of today, **{{days_elapsed}} days** have passed without the determination required by Government Code § 7922.535(a), which obligates an agency to respond within 10 days (extendable once by 14 days under § 7922.535(b) upon written notice, which was not provided).

Failure to respond violates the CPRA and Article I, § 3(b) of the California Constitution. If I do not receive the required determination and a production schedule within **10 days** of this letter, I will pursue enforcement under Government Code § 7923.000 et seq. by petition for writ of mandate. Should litigation be necessary, the court **must** award reasonable attorney's fees and costs to a prevailing requester under Government Code § 7923.115.

I remain willing to discuss reasonable narrowing or a rolling production. Please direct your response to {{requester_email}}.

Sincerely,
{{requester_name}}
{{requester_org}}

**Attachment:** Original request of {{original_request_date}}

---
*Note: CPRA enforcement is by writ petition in superior court, not an administrative complaint — this letter is the standard pre-litigation step that triggers most compliance. `pipeline/deadlines.py` generates these automatically for overdue agencies. Have an attorney review before filing any actual petition; a petition template is in `templates/cpra_writ_petition_outline.md`.*
