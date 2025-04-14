CREATE OR REPLACE FUNCTION subscription_instance_fields_as_json(sub_inst_id uuid)
    RETURNS jsonb
    LANGUAGE sql
    STABLE PARALLEL SAFE AS
$func$
select jsonb_object_agg(rts.key, rts.val)
from (select attr.key,
             attr.val
      from subscription_instances si
               join product_blocks pb ON si.product_block_id = pb.product_block_id
               cross join lateral (
          values ('subscription_instance_id', to_jsonb(si.subscription_instance_id)),
                 ('owner_subscription_id', to_jsonb(si.subscription_id)),
                 ('name', to_jsonb(pb.name))
          ) as attr(key, val)
      where si.subscription_instance_id = sub_inst_id
      union all
      select rt.resource_type                            key,
             jsonb_agg(siv.value ORDER BY siv.value ASC) val
      from subscription_instance_values siv
               join resource_types rt on siv.resource_type_id = rt.resource_type_id
      where siv.subscription_instance_id = sub_inst_id
      group by rt.resource_type) as rts
$func$;


CREATE OR REPLACE FUNCTION subscription_instance_as_json(sub_inst_id uuid)
    RETURNS jsonb
    LANGUAGE sql
    STABLE PARALLEL SAFE AS
$func$
select subscription_instance_fields_as_json(sub_inst_id) ||
       coalesce(jsonb_object_agg(depends_on.block_name, depends_on.block_instances), '{}'::jsonb)
from (select sir.domain_model_attr                                                                    block_name,
             jsonb_agg(subscription_instance_as_json(sir.depends_on_id) ORDER BY sir.order_id ASC) as block_instances
      from subscription_instance_relations sir
      where sir.in_use_by_id = sub_inst_id
        and sir.domain_model_attr is not null
      group by block_name) as depends_on
$func$;
