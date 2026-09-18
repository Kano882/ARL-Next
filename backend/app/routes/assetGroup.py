from bson import ObjectId
from pymongo import UpdateOne
from flask_restx import fields, Namespace
from app.utils import get_logger, auth
from app import utils
from . import base_query_fields, ARLResource, get_arl_parser
from app.modules import ErrorMsg

ns = Namespace('asset_group', description="资产集团分组")
logger = get_logger()

base_fields = {
    'name': fields.String(description="集团名称", required=True),
    'description': fields.String(description="集团描述"),
    'sort_order': fields.Integer(description="排序序号")
}

add_asset_group_fields = ns.model('addAssetGroup', base_fields)

edit_base_fields = base_fields.copy()
edit_base_fields.update({
    '_id': fields.String(description="集团ID", required=True)
})
edit_asset_group_fields = ns.model('editAssetGroup', edit_base_fields)

delete_asset_group_fields = ns.model('deleteAssetGroup', {
    '_id': fields.String(description="集团ID", required=True)
})

reorder_asset_group_fields = ns.model('reorderAssetGroup', {
    'order_ids': fields.List(fields.String, description="按顺序排列的集团ID列表", required=True)
})

get_asset_group_fields = base_query_fields.copy()
get_asset_group_fields.update({
    'name': fields.String(description="集团名称")
})

@ns.route('/')
class ARLAssetGroup(ARLResource):
    parser = get_arl_parser(get_asset_group_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        获取全部集团列表，并统计 scope_count
        """
        args = self.parser.parse_args()
        if not args.get('order'):
            args['order'] = '+sort_order,-_id'
        if not args.get('size'):
            args['size'] = 1000
        data = self.build_data(args=args, collection='asset_group')
        
        # Calculate scope_count for each group
        for item in data.get('items', []):
            group_id = str(item.get('_id', ''))
            if group_id:
                count = utils.conn_db('asset_scope').count_documents({'group_id': group_id})
                item['scope_count'] = count
            else:
                item['scope_count'] = 0
                
        return data

    @auth
    @ns.expect(add_asset_group_fields)
    def post(self):
        """
        新建集团
        """
        args = self.parse_args(add_asset_group_fields)
        name = args.get('name', '').strip()
        description = args.get('description', '')
        
        if not name:
            return utils.build_ret("参数错误", {"error": "集团名称不能为空"})
            
        existing = utils.conn_db('asset_group').find_one({'name': name})
        if existing:
            return utils.build_ret("参数错误", {"error": "集团名称已存在"})
            
        # 自动计算下一个 sort_order
        max_doc = utils.conn_db('asset_group').find_one({'sort_order': {'$exists': True}}, sort=[('sort_order', -1)])
        next_order = (max_doc.get('sort_order', -1) if max_doc else -1) + 1

        now = utils.curr_date()
        insert_data = {
            "name": name,
            "description": description,
            "sort_order": next_order,
            "created_at": now,
            "updated_at": now
        }
        
        try:
            res = utils.conn_db('asset_group').insert_one(insert_data)
            insert_data['_id'] = str(res.inserted_id)
            insert_data.pop('created_at', None)
            insert_data.pop('updated_at', None)
            return utils.build_ret(ErrorMsg.Success, insert_data)
        except Exception as e:
            logger.error(f"create asset_group error, detail={e}")
            return utils.build_ret(ErrorMsg.Error, {"error": "数据库写入异常"})


@ns.route('/edit/')
class EditARLAssetGroup(ARLResource):

    @auth
    @ns.expect(edit_asset_group_fields)
    def post(self):
        """
        重命名/修改集团
        """
        args = self.parse_args(edit_asset_group_fields)
        group_id = args.get('_id')
        name = args.get('name', '').strip()
        description = args.get('description', '')
        
        if not name:
            return utils.build_ret("参数错误", {"error": "集团名称不能为空"})
            
        try:
            obj_id = ObjectId(group_id)
        except Exception:
            return utils.build_ret("参数错误", {"error": "无效的集团ID"})
            
        existing = utils.conn_db('asset_group').find_one({'name': name, '_id': {'$ne': obj_id}})
        if existing:
            return utils.build_ret("参数错误", {"error": "集团名称已存在"})
            
        try:
            update_data = {
                "name": name,
                "description": description,
                "updated_at": utils.curr_date()
            }
            utils.conn_db('asset_group').update_one({'_id': obj_id}, {'$set': update_data})
            # Sync to asset_scope
            utils.conn_db('asset_scope').update_many(
                {'group_id': group_id},
                {'$set': {'group_name': name}}
            )
            return utils.build_ret(ErrorMsg.Success, {"_id": group_id, "name": name})
        except Exception as e:
            logger.error(f"edit asset_group error, detail={e}")
            return utils.build_ret(ErrorMsg.Error, {"error": "数据库更新异常"})


@ns.route('/delete/')
class DeleteARLAssetGroup(ARLResource):

    @auth
    @ns.expect(delete_asset_group_fields)
    def post(self):
        """
        删除集团
        """
        args = self.parse_args(delete_asset_group_fields)
        group_id = args.get('_id')
        
        try:
            obj_id = ObjectId(group_id)
        except Exception:
            return utils.build_ret("参数错误", {"error": "无效的集团ID"})
            
        # check scope_count
        count = utils.conn_db('asset_scope').count_documents({'group_id': group_id})
        if count > 0:
            return utils.build_ret("参数错误", {"error": f"该集团下仍有 {count} 个资产组，请先移除或划转下属资产组"})
            
        try:
            utils.conn_db('asset_group').delete_one({'_id': obj_id})
            # fallback cleanup
            utils.conn_db('asset_scope').update_many(
                {'group_id': group_id},
                {'$unset': {'group_id': "", 'group_name': ""}}
            )
            return utils.build_ret(ErrorMsg.Success, {"_id": group_id})
        except Exception as e:
            logger.error(f"delete asset_group error, detail={e}")
            return utils.build_ret(ErrorMsg.Error, {"error": "数据库删除异常"})


@ns.route('/reorder/')
class ReorderARLAssetGroup(ARLResource):

    @auth
    @ns.expect(reorder_asset_group_fields)
    def post(self):
        """
        批量更新集团分组排序
        """
        args = self.parse_args(reorder_asset_group_fields)
        order_ids = args.get('order_ids') or []
        
        if not isinstance(order_ids, list) or len(order_ids) == 0:
            return utils.build_ret("参数错误", {"error": "order_ids 不能为空且必须为列表"})
            
        operations = []
        now = utils.curr_date()
        for idx, gid in enumerate(order_ids):
            try:
                obj_id = ObjectId(gid)
                operations.append(
                    UpdateOne(
                        {'_id': obj_id},
                        {'$set': {'sort_order': idx, 'updated_at': now}}
                    )
                )
            except Exception:
                continue
                
        if not operations:
            return utils.build_ret("参数错误", {"error": "未包含有效的集团ID"})
            
        try:
            result = utils.conn_db('asset_group').bulk_write(operations, ordered=False)
            return utils.build_ret(ErrorMsg.Success, {
                "matched_count": result.matched_count,
                "modified_count": result.modified_count
            })
        except Exception as e:
            logger.error(f"reorder asset_group error, detail={e}")
            return utils.build_ret(ErrorMsg.Error, {"error": "数据库批量写入异常"})

