-- TODO rename functions to something better


CREATE OR REPLACE FUNCTION get_subscription_instance_fields(sub_inst_id uuid, mapping jsonb)
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
--           values ('subscription_instance_id', si.subscription_instance_id::text),
--                  ('owner_subscription_id', si.subscription_id::text),
--                  ('name', pb.name)
            values ('subscription_instance_id', to_jsonb(si.subscription_instance_id)),
                 ('owner_subscription_id', to_jsonb(si.subscription_id)),
                 ('name', to_jsonb(pb.name))
          ) as attr(key, val)
      where si.subscription_instance_id = sub_inst_id
      union

--       select rt.resource_type key,
--              siv.value        val
--       from subscription_instance_values siv
--             join resource_types rt on siv.resource_type_id = rt.resource_type_id
--       where siv.subscription_instance_id = sub_inst_id
--       group by rt.resource_type, siv.value

      select rt.resource_type key,
--              to_jsonb(siv.value)
             case
                 when (config.is_array is null) then to_jsonb(siv.value)
                 else coalesce(jsonb_agg(siv.value) filter (where siv.value is not null), '[]')
                 end          as val
      from subscription_instances si
               join product_blocks pb on si.product_block_id = pb.product_block_id
               join product_block_resource_types pbrt on pb.product_block_id = pbrt.product_block_id
               join resource_types rt on pbrt.resource_type_id = rt.resource_type_id
               left join subscription_instance_values siv on (rt.resource_type_id = siv.resource_type_id and
                                                              siv.subscription_instance_id =
                                                              si.subscription_instance_id)
               left join JSONB_ARRAY_ELEMENTS(mapping -> 'resource_type_lists') AS config(is_array)
                         on ((config.is_array -> 'product_block') = to_jsonb(pb.name) and
                             (config.is_array -> 'resource_type') = to_jsonb(rt.resource_type))
      where si.subscription_instance_id = sub_inst_id
      group by rt.resource_type, siv.value, config.is_array
      )
         as rts
$func$;



CREATE OR REPLACE FUNCTION get_subscription_instance(sub_inst_id uuid, mapping jsonb)
    RETURNS jsonb
    LANGUAGE sql
    STABLE PARALLEL SAFE AS
$func$
select get_subscription_instance_fields(sub_inst_id, mapping) ||
       coalesce(jsonb_object_agg(depends_on.block_name, depends_on.block_instances), '{}'::jsonb)
from (select sir.domain_model_attr                                       block_name,
             jsonb_agg(get_subscription_instance(sir.depends_on_id, mapping)) as block_instances
      from subscription_instance_relations sir
      where sir.in_use_by_id = sub_inst_id
      group by block_name) as depends_on
$func$;
