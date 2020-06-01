""""""

from threading import Condition
from datetime import datetime
from typing import Dict, Set, List
from copy import copy

import chronos_api

from vnpy.event import Event
from vnpy.trader.event import EVENT_TIMER

"""枚举类"""
from vnpy.trader.constant import (
    Direction,
    Offset,
    Exchange,
    OrderType,
    Product,
    Status,
    Interval
)

from vnpy.trader.gateway import BaseGateway
from vnpy.trader.object import (
    TickData,
    OrderData,
    TradeData,
    PositionData,
    BarData,
    AccountData,
    ContractData,
    OrderRequest,
    CancelRequest,
    SubscribeRequest,
    HistoryRequest
)
from vnpy.trader.utility import get_folder_path

STATUS_CHRONOS2VT = {
    chronos_api.OrderStatusType.kOtNotApproved: Status.SUBMITTING,
    chronos_api.OrderStatusType.kOtNotReported: Status.SUBMITTING,
    chronos_api.OrderStatusType.kOtWaitReporting: Status.SUBMITTING,
    chronos_api.OrderStatusType.kOtReported: Status.NOTTRADED,
    chronos_api.OrderStatusType.kOtCanceling: Status.SUBMITTING,
    chronos_api.OrderStatusType.kOtCanceled: Status.CANCELLED,
    chronos_api.OrderStatusType.kOtMatchedCanceling: Status.SUBMITTING,
    chronos_api.OrderStatusType.kOtMatchedCanceled: Status.CANCELLED,
    chronos_api.OrderStatusType.kOtCanceled: Status.CANCELLED,
    chronos_api.OrderStatusType.kOtPartMatched: Status.PARTTRADED,
    chronos_api.OrderStatusType.kOtMatchedAll: Status.ALLTRADED,
    chronos_api.OrderStatusType.kOtBad: Status.REJECTED,
    chronos_api.OrderStatusType.kOtRiskBlocked: Status.REJECTED
}

DIRECTION_VT2CHRONOS = {
    Direction.LONG: chronos_api.DirectiveType.kDtBuy,
    Direction.SHORT: chronos_api.DirectiveType.kDtSell
}
DIRECTION_CHRONOS2VT = {v: k for k, v in DIRECTION_VT2CHRONOS.items()}
DIRECTION_CHRONOS2VT[chronos_api.DirectionType.kDtLong] = Direction.LONG
DIRECTION_CHRONOS2VT[chronos_api.DirectionType.kDtShort] = Direction.SHORT

ORDERTYPE_VT2CHRONOS = {
    OrderType.LIMIT: chronos_api.ExecutionType.kExeLimit,
    OrderType.MARKET: chronos_api.ExecutionType.kExeAnyPrice
}
ORDERTYPE_CHRONOS2VT = {v: k for k, v in ORDERTYPE_VT2CHRONOS.items()}

OFFSET_VT2CHRONOS = {
    Offset.NONE: chronos_api.OffsetFlagType.kOftNone,
    Offset.OPEN: chronos_api.OffsetFlagType.kOftOpen,
    Offset.CLOSE: chronos_api.OffsetFlagType.kOftClose,
    Offset.CLOSETODAY: chronos_api.OffsetFlagType.kOftCloseToday,
    Offset.CLOSEYESTERDAY: chronos_api.OffsetFlagType.kOftCloseYesterday,
}
OFFSET_CHRONOS2VT = {v: k for k, v in OFFSET_VT2CHRONOS.items()}

EXCHANGE_CHRONOS2VT = {
    chronos_api.MarketType.MARKET_CFE: Exchange.CFFEX,
    chronos_api.MarketType.MARKET_SHF: Exchange.SHFE,
    chronos_api.MarketType.MARKET_CZC: Exchange.CZCE,
    chronos_api.MarketType.MARKET_DCE: Exchange.DCE,
    chronos_api.MarketType.MARKET_SHA: Exchange.SSE,
    chronos_api.MarketType.MARKET_SZA: Exchange.SZSE,
}

PRODUCT_CHRONOS2VT = {
    chronos_api.Variety.VARIETY_STOCK: Product.EQUITY,
    chronos_api.Variety.VARIETY_BOND: Product.BOND,
    chronos_api.Variety.VARIETY_FUND: Product.FUND,
    chronos_api.Variety.VARIETY_SPOT: Product.SPOT,
    chronos_api.Variety.VARIETY_MONEY_MARKET: Product.BOND,
    chronos_api.Variety.VARIETY_INDEX: Product.INDEX,
    chronos_api.Variety.VARIETY_FUTURE: Product.FUTURES,
    chronos_api.Variety.VARIETY_OPTION: Product.OPTION,
    chronos_api.Variety.VARIETY_WARRANT: Product.WARRANT,
    chronos_api.Variety.VARIETY_STOCK_OPTION: Product.OPTION
}

ERROR_MSG = {
    0: "成功",
    -1001: "未初始化",
    -1002: "初始化失败",
    -1003: "重复初始化",
    -1004: "未连接到服务器",
    -1005: "请求发送失败",
    -1006: "不合法的参数调用",
    -1007: "不合法的请求参数",
    -1008: "不合法的账户",
    -1009: "不合法的应答",
    -1010: "不支持的请求调用",
    -1011: "未登录",
    -1012: "重复登录",
    -1013: "不合法的登录",
    -1014: "不合法的TERM_ID",
    -1015: "重复请求ID(API内请求ID不允许重复)",
    -1016: "请求数量超出限制",
    -1017: "不合法的UKey值(订阅ukey不允许为0)"
}

"""???"""
ukey_symbol_map: Dict[str, str] = {}
symbol_ukey_map: Dict[str, str] = {}
ukey_name_map: Dict[str, str] = {}


class ChronosGateway(BaseGateway):
    """
    VN Trader Gateway for Chronos connection.
    """

    default_setting = {
        "用户名": "",
        "密码": "",
        "客户号": 0,
        "交易服务器": "ssl://139.159.228.12:8001",
        "行情服务器": "ssl://139.159.228.12:8001",
    }

    exchanges = [
        Exchange.CFFEX,
        Exchange.SHFE,
        Exchange.DCE,
        Exchange.CZCE,
        Exchange.SSE,
        Exchange.SZSE
    ]

    def __init__(self, event_engine) -> None:
        """Constructor"""
        super().__init__(event_engine, "CHRONOS")

        self.quote_api: "ChronosQuoteApi" = ChronosQuoteApi(self)
        self.trade_api: "ChronosTradeApi" = ChronosTradeApi(self)

    def connect(self, setting: dict) -> None:
        """"""
        username = setting["用户名"]
        password = setting["密码"]
        account_id = setting["客户号"]
        trade_address = setting["交易服务器"]
        quote_address = setting["行情服务器"]
        srv_id = chronos_api.ServiceID.kServiceCOMS

        self.trade_api.connect(trade_address, username, password, account_id, srv_id)
        self.quote_api.connect(quote_address, username, password)

    def subscribe(self, req: SubscribeRequest) -> None:
        """"""
        self.quote_api.subscribe(req)

    def send_order(self, req: OrderRequest) -> str:
        """"""
        return self.trade_api.send_order(req)

    def cancel_order(self, req: CancelRequest) -> None:
        """"""
        self.trade_api.cancel_order(req)

    def query_account(self) -> None:
        """"""
        self.trade_api.query_account()

    def query_position(self) -> None:
        """"""
        self.trade_api.query_position()

    def query_order(self) -> None:
        """"""
        self.trade_api.query_order()

    def query_history(self, req: HistoryRequest) -> List[BarData]:
        """"""
        return self.quote_api.query_history(req)

    def close(self) -> None:
        """"""
        self.quote_api.stop()
        self.trade_api.stop()

    def init_query(self) -> None:
        """"""
        self.query_account()
        self.query_position()
        self.query_order()


class ChronosTradeApi(chronos_api.TradeSpi):
    """"""

    def __init__(self, gateway: ChronosGateway) -> None:
        """"""
        super().__init__()

        self.gateway: ChronosGateway = gateway
        self.gateway_name: str = gateway.gateway_name

        self.api: chronos_api.TradeApi = None
        self.username: str = ""
        self.password: str = ""
        self.account_id: int = 0
        self.srv_id: chronos_api.ServiceID = None

        self.connect_status: bool = False
        self.login_status: bool = False
        self.reqid: int = 0
        self.order_ref: int = 0
        self.trade_id: int = 0

        self.orders: Dict[str, OrderData] = {}
        self.ods: Dict[str, chronos_api.OrderStatus] = {}

    def OnConnected(self) -> None:
        """
        当使用 API 的应用与前置网关系统(FGS)或后台服务建立连接时(尚未登录)，
        该方法被调用
        """
        self.connect_status = True
        self.gateway.write_log("交易服务器连接成功")
        self.login()

    def OnDisconnect(self) -> None:
        """
        当使用 API 的应用与前置网关系统(FGS)或后台服务连接断开时，
        该方法被调用
        """
        self.connect_status = False
        self.login_status = False
        self.gateway.write_log("交易服务器连接断开")

    def OnRspCancelOrder(self, cancel_order_ans) -> None:
        """
        当使用 API 的应用发出撤单委托后，
        后台服务做出响应时，该方法被调用
        """
        pass

    def OnRspError(self, rsp_code, request_id) -> None:
        """
        当 API 应用发出请求后，
        后台服务处理请求发生错误时做出响应，该方法被调用
        """
        self.gateway.write_log(rsp_code.ret_msg)

    def OnRspOrderRtn(self, order_status: chronos_api.OrderStatus, fund=None, position=None) -> None:
        """
        当委托的订单在后台服务发送状态变化，
        后台服务将进行推送时，该方法被调用
        """
        self.update_order(order_status, True)

        if fund:
            self.update_account(fund)

        if position:
            self.update_position(position)

    def OnRspQueryFund(self, rsp_code, fund_arry, request_id) -> None:
        """
        当使用 API 的应用发出资金查询请求后，
        后台服务返回查询回来的资金数据时，该方法被调用
        """
        for fund in fund_arry:
            self.update_account(fund)

    def OnRspQueryOrder(self, rsp_code, order_status_array, request_id) -> None:
        """
        当使用 API 的应用发出订单查询请求后，
        后台服务返回查询回来的订单数据时，该方法被调用
        """
        try:
            for order_status in order_status_array:
                order_status.od_price = order_status.od_price / 10000
                self.update_order(order_status)
        except:
            import traceback
            traceback.print_exc()

    def OnRspQueryPosition(self, rsp_code, position_array, request_id) -> None:
        """
        当使用 API 的应用发出持仓查询请求后，
        后台服务返回查询回来的持仓数据时，该方法被调用
        """
        for chronos_position in position_array:
            self.update_position(chronos_position)

    def OnRspQueryUkeyInfo(
            self,
            rsp_code: chronos_api.RspCode,
            handle: chronos_api.UkeyHandle,
            request_id: int
    ) -> None:
        """
        当 API 应用发出 UKEY 信息查询请求后，
        后台服务做出响应时，该方法被调用
        """
        pass

    def OnRspSendOrder(self, order_status: chronos_api.OrderStatus) -> None:
        """
        当使用 API 的应用发出订单委托请求后，
        后台服务做出响应时，该方法被调用
        """
        self.update_order(order_status)

    def OnRspUserLogin(self, login_ans: chronos_api.LoginAns) -> None:
        """
        当使用 API 的应用发出登录请求后，
        后台服务做出响应时，该方法被调用
        """
        if not login_ans.ret_code:
            self.login_status = True
            self.term_id = login_ans.id
            self.gateway.write_log("交易服务器登录成功")
        else:
            self.gateway.write_log(login_ans.ret_msg)

    def OnRspUserLogout(self, logout_ans) -> None:
        """
        当使用 API 的应用发出登出请求后或是后台服务主动给 API 应用发出登出通知时，
        该方法被调用
        """
        pass

    def update_order(
            self,
            order_status: chronos_api.OrderStatus,
            rtn: bool = False
    ) -> None:
        """"""
        orderid = f"{order_status.od_term_id}.{order_status.od_order_ref}"
        order = self.orders.get(orderid, None)

        if not order:
            symbol, exchange = ukey_symbol_map[order_status.od_ukey]

            order = OrderData(
                symbol=symbol,
                exchange=exchange,
                orderid=orderid,
                direction=DIRECTION_CHRONOS2VT[order_status.od_directive],
                offset=OFFSET_CHRONOS2VT[order_status.od_offset_flag],
                price=order_status.od_price,
                volume=order_status.od_qty,
                time=convert_time(order_status.od_order_time),
                gateway_name=self.gateway_name
            )

            self.orders[order.orderid] = order

        order.traded = order_status.trade_qty
        order.status = STATUS_CHRONOS2VT[order_status.status]

        if rtn and order.status == Status.REJECTED:
            self.gateway.write_log(f"委托失败：{order_status.message}")

        self.gateway.on_order(copy(order))

        # Calculate trade data
        old_status = self.ods.get(orderid, None)

        if not old_status:
            trade_volume = order_status.trade_qty
            trade_amount = order_status.trade_amt
        else:
            trade_volume = order_status.trade_qty - old_status.trade_qty
            trade_amount = order_status.trade_amt - old_status.trade_amt

        self.ods[orderid] = order_status

        if not trade_volume:
            return

        self.trade_id += 1
        trade = TradeData(
            symbol=order.symbol,
            exchange=order.exchange,
            orderid=order.orderid,
            tradeid=str(self.trade_id),
            direction=order.direction,
            offset=order.offset,
            price=trade_amount / trade_volume,
            volume=trade_volume,
            time=convert_time(order_status.trade_time),
            gateway_name=self.gateway_name
        )
        self.gateway.on_trade(trade)

    def update_account(self, fund: chronos_api.Fund):
        """"""
        account = AccountData(
            accountid=fund.account_id,
            balance=fund.total_amt,
            frozen=fund.frozen_amt,
            gateway_name=self.gateway_name
        )

        self.gateway.on_account(account)

    def update_position(self, chronos_position: chronos_api.Position):
        """"""
        symbol, exchange = ukey_symbol_map[chronos_position.ukey]

        position = PositionData(
            symbol=symbol,
            exchange=exchange,
            direction=DIRECTION_CHRONOS2VT[chronos_position.direction],
            volume=chronos_position.total_qty,
            frozen=chronos_position.locked_avl_qty,
            price=chronos_position.total_cost / chronos_position.total_qty,
            pnl=chronos_position.mtm_position_pl,
            yd_volume=chronos_position.overnight_qty,
            gateway_name=self.gateway_name
        )

        self.gateway.on_position(position)

    def connect(
            self,
            address: str,
            username: str,
            password: str,
            account_id: int,
            srv_id: chronos_api.ServiceID
    ) -> None:
        """"""
        self.username = username
        self.password = password
        self.srv_id = srv_id
        self.account_id = account_id

        path = get_folder_path(self.gateway_name.lower())
        self.api = chronos_api.TradeApi(0, str(path))
        self.api.Initialize(address, self, srv_id, 0)

    def login(self):
        """"""
        trade_user = chronos_api.TradeUser()
        trade_user.trade_identity = chronos_api.TradeIdentity.kTiPortfolio
        trade_user.data_mode = chronos_api.DataMode.kDmAccountAll
        trade_user.account_type = chronos_api.AccountType.kActGeneral
        trade_user.bacid = ""
        trade_user.bacidcard = ""
        trade_user.password = ""
        trade_user.id = self.account_id

        fgs_user = chronos_api.FgsUser()
        fgs_user.login_code = self.username
        fgs_user.password = self.password
        fgs_user.login_type = chronos_api.LoginType.kUserName

        self.api.ReqUserLogin(trade_user, fgs_user)

    def send_order(self, req: OrderRequest) -> str:
        """"""
        ukey = symbol_ukey_map.get((req.symbol, req.exchange), "")
        if not ukey:
            self.gateway.write_log("委托失败，找不到合约：{}".format(req.vt_symbol))
            return ""

        self.order_ref += 1

        chronos_req = chronos_api.Order()
        chronos_req.ukey = ukey
        chronos_req.order_ref = self.order_ref
        chronos_req.directive = DIRECTION_VT2CHRONOS[req.direction]
        chronos_req.offset_flag = OFFSET_VT2CHRONOS[req.offset]
        chronos_req.hedge_flag = chronos_api.HedgeFlagType.kHftSpeculation
        chronos_req.execution = ORDERTYPE_VT2CHRONOS[req.type]
        chronos_req.account_id = self.account_id
        chronos_req.qty = int(req.volume)
        chronos_req.price = req.price * 10000

        n = self.api.ReqSendOrder(chronos_req)

        if not n:
            orderid = f"{chronos_req.term_id}.{self.order_ref}"
            order = req.create_order_data(orderid, self.gateway_name)
            self.gateway.on_order(order)

            return order.vt_orderid
        else:
            error_msg = ERROR_MSG[n]
            self.gateway.write_log("委托失败：{}".format(error_msg))

            return ""

    def cancel_order(self, req: CancelRequest) -> None:
        """"""
        term_id, order_ref = req.orderid.split(".")

        chronos_req = chronos_api.CancelOrder()
        chronos_req.account_id = self.account_id
        chronos_req.order_ref = int(order_ref)
        chronos_req.term_id = int(term_id)

        self.api.ReqCancelOrder(chronos_req)

    def query_order(self) -> None:
        """"""
        chronos_req = chronos_api.QueryOrder()
        chronos_req.account_id = self.account_id

        self.reqid += 1
        self.api.ReqQueryOrder(chronos_req, self.reqid)

    def query_account(self) -> None:
        """"""
        if not self.login_status:
            return

        chronos_req = chronos_api.QueryFund()
        chronos_req.account_id = self.account_id

        self.reqid += 1
        self.api.ReqQueryFund(chronos_req, self.reqid)

    def query_position(self) -> None:
        """"""
        if not self.login_status:
            return

        chronos_req = chronos_api.QueryPosition()
        chronos_req.account_id = self.account_id

        self.reqid += 1
        self.api.ReqQueryPosition(chronos_req, self.reqid)

    def stop(self) -> None:
        """"""
        if self.api:
            self.api.Release()


class ChronosQuoteApi(chronos_api.QuoteSpi):
    """"""

    def __init__(self, gateway: ChronosGateway) -> None:
        """"""
        super().__init__()

        self.gateway: ChronosGateway = gateway
        self.gateway_name: str = gateway.gateway_name

        self.api: chronos_api.QuoteApi = None
        self.username: str = ""
        self.password: str = ""

        self.connect_status: bool = False
        self.login_status: bool = False
        self.subscribed: Set = set()
        self.reqid: int = 0

        self.history_req: HistoryRequest = None
        self.history_condition: Condition = Condition()
        self.history_buf: List[BarData] = []

        self.reqid_market_map: Dict[int: chronos_api.MarketType] = {}

    def OnConnected(self) -> None:
        """"""
        self.connect_status = True
        self.gateway.write_log("行情服务器连接成功")
        self.login()

    def OnDisconnect(self) -> None:
        """"""
        self.connect_status = False
        self.login_status = False
        self.gateway.write_log("行情服务器连接断开")

    def OnRspQueryUkeyInfo(
            self,
            rsp_code: chronos_api.RspCode,
            handle: chronos_api.UkeyHandle,
            request_id: int
    ) -> None:
        """当 API 应用发出 UKEY 信息查询请求后，后台服务做出响应时，该方法被调用"""
        pass

    def OnRspUserLogin(self, login_ans: chronos_api.LoginAns) -> None:
        """当使用 API 的应用发出登录请求后，后台服务做出响应时，该方法被调用"""
        if not login_ans.ret_code:
            self.login_status = True
            self.gateway.write_log("行情服务器登录成功")

            self.query_contract()
        else:
            self.gateway.write_log(login_ans.ret_msg)

    def OnRspUserLogout(self, logout_ans) -> None:
        """
        当使用 API 的应用发出登出请求后或是后台服务主动给 API 应用发出登出通知时，该方法被调用
        """
        pass

    def OnRspError(self, rsp_code: chronos_api.RspCode, request_id: int) -> None:
        """"""
        self.gateway.write_log(rsp_code.ret_msg)

    def OnRspQuerySecumaster(
            self,
            rsp_code: chronos_api.RspCode,
            handle: chronos_api.UkeyHandle,
            request_id: int
    ) -> None:
        """当 API 应用发出 Secumaster 信息查询请求后，后台服务做出响应时，该方法被调用"""
        market = self.reqid_market_map.pop(request_id)

        _, infos = handle.GetSecurityInfoByType(
            market,
            chronos_api.Variety.VARIETY_ALL
        )

        for info in infos:
            contract = ContractData(
                symbol=str(info.market_code),
                exchange=EXCHANGE_CHRONOS2VT[info.market_id],
                name=info.market_abbr,
                product=PRODUCT_CHRONOS2VT[info.major_type],
                size=info.multiplier,
                pricetick=info.tick_size / 10000,
                min_volume=info.min_order_size,
                net_position=True,
                history_data=True,
                gateway_name=self.gateway_name
            )

            ukey_symbol_map[info.ukey] = (contract.symbol, contract.exchange)
            symbol_ukey_map[(contract.symbol, contract.exchange)] = info.ukey
            ukey_name_map[info.ukey] = contract.name

            self.gateway.on_contract(contract)

        self.gateway.write_log(f"{contract.exchange.value}合约信息查询成功")

        if not self.reqid_market_map:
            self.gateway.init_query()

    def OnRspQueryFuturesContraCHRONOSro(self, rsp_code, ukey_handle, request_id) -> None:
        """"""
        pass

    def OnRspQueryMarket(self, rsp_code, ukey_handle, request_id) -> None:
        """当 API 应用发出市场信息查询请求后，后台服务做出响应时，该方法被调用"""
        pass

    def OnRspQueryEtfComponent(self, rsp_code, ukey_handle, request_id) -> None:
        """"""
        pass

    def OnRspQueryRightsIssue(self, rsp_code, data_list, request_id, page_num, page_cur) -> None:
        """当 API 应用发出 A 股配股数据查询请求后，后台服务做出响应时，该方法被调用"""
        pass

    def OnRspQueryDividend(self, rsp_code, data_list, request_id, page_num, page_cur) -> None:
        """当 API 应用发出 A 股分红数据查询请求后，后台服务做出响应时，该方法被调用"""
        pass

    def OnRspQueryMdSnapshot(
            self,
            rsp_code: chronos_api.RspCode,
            data_list: List[chronos_api.MdSnapshot],
            request_id: int,
            page_num: int,
            page_cur: int
    ) -> None:
        """当 API 应用发出历史行情快照信息查询请求后，后台服务做出响应时，该方法被调用"""
        for snapshot in data_list:
            self.update_tick(snapshot)

    def OnRspQueryMdTransaction(self, rsp_code, data_list, request_id, page_num, page_cur) -> None:
        """
        当 API 应用发出历史行情逐笔成交信息查询请求后，后台服务做出响应时，该方法被调用
        """
        pass

    def OnRspQueryMdOrder(self, rsp_code, data_list, request_id, page_num, page_cur) -> None:
        """
        当 API 应用发出历史行情逐笔委托信息查询请求后，后台服务做出响应时，该方法被调用
        """
        pass

    def OnRspQueryMdOrderQueue(self, rsp_code, data_list, request_id, page_num, page_cur) -> None:
        """
        当 API 应用发出历史行情委托队列信息查询请求后，后台服务做出响应时，该方法被调用
        """
        pass

    def OnRspQueryMdKLineMinute(
            self,
            rsp_code: chronos_api.RspCode,
            data_list: List[chronos_api.MdKLine],
            request_id: int,
            page_num: int,
            page_cur: int
    ) -> None:
        """当 API 应用发出历史行情分钟线信息查询请求后，后台服务做出响应时，该方法被调用"""
        self.process_history(rsp_code, data_list, request_id, page_num, page_cur)

    def OnRspQueryMdKLineDay(self, rsp_code, data_list, request_id, page_num, page_cur) -> None:
        """当 API 应用发出历史行情日线信息查询请求后，后台服务做出响应时，该方法被调用"""
        self.process_history(rsp_code, data_list, request_id, page_num, page_cur)

    def OnRtnMdSnapshot(self, snapshot: chronos_api.MdSnapshot) -> None:
        """
        当 API 应用发出订阅实时行情快照请求后，后台服务在有行情数据时会进行数据推送，此时该方法将被调用
        """
        self.update_tick(snapshot)

    def OnRtnMdTransaction(self, transaction) -> None:
        """"""
        pass

    def OnRtnMdOrder(self, order) -> None:
        """"""
        pass

    def OnRtnMdOrderQueue(self, order_queue) -> None:
        """"""
        pass

    def OnRtnMdKLine(self, kline) -> None:
        """"""
        pass

    def connect(self, address: str, username: str, password: str) -> None:
        """"""
        self.username = username
        self.password = password

        path = get_folder_path(self.gateway_name.lower())
        self.api = chronos_api.QuoteApi(0, str(path))

        self.api.Initialize(address, self)

    def login(self):
        """"""
        user = chronos_api.FgsUser()
        user.login_code = self.username
        user.password = self.password
        user.login_type = chronos_api.LoginType.kUserName

        self.api.ReqUserLogin(user)

    def subscribe(self, req: SubscribeRequest) -> None:
        """"""
        ukey = symbol_ukey_map.get((req.symbol, req.exchange), "")
        if not ukey:
            self.gateway.write_log("订阅行情失败，不支持该合约：{}".format(req.vt_symbol))
            return

        # Get latest snapshot
        self.reqid += 1
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(now)
        end = self.api.TimeFromString(now)
        print(end)
        self.api.ReqQueryMdSnapshotBackward([ukey], end, 1, self.reqid)

        # Subscribe to stream update
        self.api.SubscribeMdSnapshot([ukey])

    def stop(self) -> None:
        """"""
        if self.api:
            self.api.Release()

    def query_contract(self) -> None:
        """"""
        # Only query China Shanghai and Shenzhen stocks
        for market in [
            chronos_api.MarketType.MARKET_CFE,
            chronos_api.MarketType.MARKET_SHF,
            chronos_api.MarketType.MARKET_DCE,
            chronos_api.MarketType.MARKET_CZC,
            chronos_api.MarketType.MARKET_SHA,
            chronos_api.MarketType.MARKET_SZA,
        ]:
            self.reqid += 1

            self.api.ReqQuerySecumasterByType(
                market,
                chronos_api.Variety.VARIETY_ALL,
                0,
                self.reqid
            )

            self.reqid_market_map[self.reqid] = market

    def query_history(self, req: HistoryRequest) -> List[BarData]:
        """"""
        self.reqid += 1
        self.history_req = req
        ukey = symbol_ukey_map[(req.symbol, req.exchange)]

        if req.interval == Interval.MINUTE:
            self.api.ReqQueryMdKLineMinute(
                [ukey],
                int(req.start.timestamp()),
                int(req.end.timestamp()),
                self.reqid
            )
        else:
            self.api.ReqQueryMdKLineDay(
                [ukey],
                req.start.timestamp(),
                req.end.timestamp(),
                self.reqid
            )

        self.history_condition.acquire()  # Wait for async data return
        self.history_condition.wait()
        self.history_condition.release()

        history = self.history_buf
        self.history_buf = []  # Create new buffer list
        self.history_req = None

        return history

    def process_history(
            self,
            rsp_code: chronos_api.RspCode,
            data_list: List[chronos_api.MdKLine],
            request_id: int,
            page_num: int,
            page_cur: int
    ) -> None:
        """"""
        # Check error msg
        if rsp_code.ret_code:
            self.gateway.write_log(rsp_code.ret_msg)

            self.history_condition.acquire()
            self.history_condition.notify()
            self.history_condition.release()

            return

        # Convert bar data
        for md_kline in data_list:
            dt = datetime.fromtimestamp(md_kline.timeus / 1000000)

            bar = BarData(
                symbol=self.history_req.symbol,
                exchange=self.history_req.exchange,
                datetime=dt,
                interval=self.history_req.interval,
                volume=md_kline.volume,
                open_price=md_kline.open / 10000,
                high_price=md_kline.high / 10000,
                low_price=md_kline.low / 10000,
                close_price=md_kline.close / 10000,
                gateway_name=self.gateway_name
            )

            self.history_buf.append(bar)

        # Check if all data returned
        if page_cur == page_num:
            self.history_condition.acquire()
            self.history_condition.notify()
            self.history_condition.release()

    def update_tick(self, snapshot: chronos_api.MdSnapshot) -> None:
        """"""
        symbol, exchange = ukey_symbol_map[snapshot.ukey]
        extra = snapshot.extra_info.as_stock_extra()

        tick = TickData(
            symbol=symbol,
            exchange=exchange,
            name=ukey_name_map.get(snapshot.ukey, ""),
            datetime=datetime.fromtimestamp(snapshot.timeus / 1000000),
            limit_up=extra.upper_limit / 10000,
            limit_down=extra.lower_limit / 10000,
            last_price=snapshot.last / 10000,
            open_price=snapshot.open / 10000,
            high_price=snapshot.high / 10000,
            low_price=snapshot.low / 10000,
            volume=snapshot.volume,
            pre_close=snapshot.pre_close / 10000,
            bid_price_1=snapshot.bid_price[0] / 10000,
            bid_price_2=snapshot.bid_price[1] / 10000,
            bid_price_3=snapshot.bid_price[2] / 10000,
            bid_price_4=snapshot.bid_price[3] / 10000,
            bid_price_5=snapshot.bid_price[4] / 10000,
            ask_price_1=snapshot.ask_price[0] / 10000,
            ask_price_2=snapshot.ask_price[1] / 10000,
            ask_price_3=snapshot.ask_price[2] / 10000,
            ask_price_4=snapshot.ask_price[3] / 10000,
            ask_price_5=snapshot.ask_price[4] / 10000,
            bid_volume_1=snapshot.bid_volume[0],
            bid_volume_2=snapshot.bid_volume[1],
            bid_volume_3=snapshot.bid_volume[2],
            bid_volume_4=snapshot.bid_volume[3],
            bid_volume_5=snapshot.bid_volume[4],
            ask_volume_1=snapshot.ask_volume[0],
            ask_volume_2=snapshot.ask_volume[1],
            ask_volume_3=snapshot.ask_volume[2],
            ask_volume_4=snapshot.ask_volume[3],
            ask_volume_5=snapshot.ask_volume[4],
            gateway_name=self.gateway_name
        )

        self.gateway.on_tick(tick)


def convert_time(data: int) -> str:
    """"""
    time_data = data >> 32
    time_str = str(time_data)
    time_str = f"{time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}"

    return time_str
