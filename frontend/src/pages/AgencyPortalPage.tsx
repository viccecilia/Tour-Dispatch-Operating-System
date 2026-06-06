import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, CalendarDays, CarFront, ChevronLeft, ChevronRight, FilePenLine, Gavel, KeyRound, ListChecks, MapPinned, Plane, Send, Settings, Table2, Undo2, Upload, UserRound } from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api, clearAgencyToken, getAgencyToken, setAgencyToken } from "@/services/apiClient";
import type { AgencyOrderChangeRequest, AgencyPortalAgency, AuctionListing, Order } from "@/types/api";

type PortalTab = "single" | "batch" | "orders" | "hall" | "mine" | "calendar" | "settings";
type HallSubView = "public" | "mine" | "publish";
type AgencyOrderKind = "包车" | "接机" | "送机";
type PublishDraftSettings = { startPrice: string; buyoutPrice: string; duration: 1 | 2 | 4; note?: string };
type BatchOrderDraft = Partial<Order> & { itinerary_pdf_file?: File };
type UploadPdfMutation = ReturnType<typeof useMutation<{ success: boolean; order_id: number; file_url: string; file_name: string }, Error, { orderId: number; file: File }>>;
type UploadReceiptMutation = ReturnType<typeof useMutation<{ success: boolean; order_id: number; file_url: string; file_name: string }, Error, { orderId: number; file: File }>>;
type UpdateFlightMutation = ReturnType<typeof useMutation<{ success: boolean; order: Order; flight: Partial<Order> }, Error, { orderId: number; payload: Partial<Order> & { lookup?: boolean; query?: boolean } }>>;
type PublishAuctionMutation = ReturnType<typeof useMutation<{ success: boolean; count: number; listings: Array<{ listing_id: number; order_id: number; oid?: string; listing_code?: string; publish_round?: number; auction_duration_hours?: number }> }, Error, { orderId: number; payload: { start_price_jpy: number; buyout_price_jpy: number; auction_duration_hours: 1 | 2 | 4; note?: string } }>>;

const today = new Date().toISOString().slice(0, 10);

const emptyOrder: Partial<Order> = {
  order_date: today,
  end_date: today,
  start_time: "09:00",
  end_time: "19:00",
  pickup_location: "",
  dropoff_location: "",
  order_type: "包车",
  vehicle_type: "",
  passenger_count: 0,
  luggage_count: 0,
  flight_number: "",
  flight_date: today,
  flight_status: "",
  guest_name: "",
  guest_contact: "",
  guide_name: "",
  guide_phone: "",
  guide_wechat: "",
  guide_line: "",
  guide_whatsapp: "",
  price: undefined,
  fee_remark: "",
  remark: "",
};

const batchTemplate = `2026-06-10 09:30 关西机场T1 -> Osaka Namba Hotel 4人 5件 Hiace 客人Zhang 080-1111-2222 52000
2026-06-10 14:00 Osaka Namba Hotel -> Kansai International Airport T1 3人 3件 Alphard 客人Li 080-2222-3333 68000`;

const charterBatchTemplate = `6.02 09:00 京都往返天桥立美山 包车 3代 绿1900Mico Yamamoto
6.02 10:00 京都-大阪 包车 3代 绿1500（司机KAKAO联系）Gayun Lee
6.06 10:00 京都-奈良-宇治-京都 包车 3代 绿 1500Mahesh Patil
6.08 08:30 京都市内 包车 10座绿 1600乃綺 施
6.14 09:00 京都往返天桥立美山 包车 3代 绿 1900 Donghan Yang
6.16 10:00 京都-宇治-奈良-大阪 包车 10座绿（英文司机）1700 Emily Childers`;

const charterTemplate = `2026-06-15 包车 09:00-18:00
酒店：Osaka Namba Hotel
行程：大阪城 -> 奈良公园 -> 京都站
车型：Hiace 6人 4件
客人：Wang 080-9999-8888
导游：Chen 090-1111-2222 微信 wx-guide Line line-guide WhatsApp 090-1111-2222
报价：120000`;

export function AgencyPortalPage() {
  const queryClient = useQueryClient();
  const [agency, setAgency] = useState<AgencyPortalAgency | null>(null);
  const [portalCode, setPortalCode] = useState("");
  const [portalPassword, setPortalPassword] = useState("");
  const [passwordForm, setPasswordForm] = useState({ current: "", next: "", confirm: "" });
  const [passwordMessage, setPasswordMessage] = useState("");
  const [form, setForm] = useState<Partial<Order>>(emptyOrder);
  const [activeTab, setActiveTab] = useState<PortalTab>("single");
  const [batchText, setBatchText] = useState(batchTemplate);
  const [batchMessage, setBatchMessage] = useState("");
  const [trackingKeyword, setTrackingKeyword] = useState("");
  const [calendarDate, setCalendarDate] = useState(today);
  const [mapOrderId, setMapOrderId] = useState<number | null>(null);
  const [requestOrderId, setRequestOrderId] = useState<number | null>(null);
  const [requestMessage, setRequestMessage] = useState("");
  const [auctionMessage, setAuctionMessage] = useState("");
  const [itineraryMessage, setItineraryMessage] = useState("");
  const [settlementMessage, setSettlementMessage] = useState("");
  const hasToken = Boolean(getAgencyToken());
  const resolvedAgency = useQuery({
    queryKey: ["agency-portal-resolve", portalCode.trim()],
    queryFn: () => api.resolveAgencyPortalAccount(portalCode.trim()),
    enabled: !hasToken && portalCode.trim().length >= 2,
    retry: false,
  });
  const orders = useQuery({ queryKey: ["agency-portal-orders", hasToken], queryFn: api.agencyPortalOrders, enabled: hasToken });
  const changeRequests = useQuery({ queryKey: ["agency-portal-change-requests", hasToken], queryFn: api.agencyPortalChangeRequests, enabled: hasToken });
  const auctionListings = useQuery({ queryKey: ["agency-portal-auction-listings", hasToken], queryFn: () => api.agencyPortalAuctionListings("listed"), enabled: hasToken, refetchInterval: 5000 });

  const orderRows = useMemo(() => orders.data || [], [orders.data]);
  const trackingRows = useMemo(() => {
    const keyword = trackingKeyword.trim().toLowerCase();
    if (!keyword) return orderRows;
    return orderRows.filter((order) =>
      [
        order.oid,
        order.order_date,
        order.pickup_location,
        order.dropoff_location,
        order.vehicle_type,
        order.guest_name,
        order.guest_contact,
        order.dispatch_status,
        order.settlement_status,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(keyword),
    );
  }, [orderRows, trackingKeyword]);

  const calendarRows = useMemo(
    () => orderRows.filter((order) => (order.order_date || "").slice(0, 10) === calendarDate),
    [calendarDate, orderRows],
  );
  const mapRows = useMemo(
    () => orderRows.filter((order) => order.dispatch_status !== "unassigned" || order.assignment_id || order.driver_name || order.plate_number),
    [orderRows],
  );

  const stats = useMemo(() => {
    const unassigned = orderRows.filter((order) => order.dispatch_status === "unassigned").length;
    const claimed = orderRows.filter((order) => ["auction_claimed", "claimed", "assigned"].includes(order.dispatch_status || "")).length;
    const pendingSettlement = orderRows.filter((order) => (order.settlement_status || "pending") === "pending").length;
    return { total: orderRows.length, unassigned, claimed, pendingSettlement };
  }, [orderRows]);

  const loginMutation = useMutation({
    mutationFn: () => api.agencyPortalLogin(portalCode.trim(), portalPassword),
    onSuccess: (result) => {
      setAgencyToken(result.token);
      setAgency(result.agency);
      setPortalPassword("");
      queryClient.invalidateQueries({ queryKey: ["agency-portal-orders"] });
    },
  });

  const changePasswordMutation = useMutation({
    mutationFn: () => api.changeAgencyPortalPassword({ current_password: passwordForm.current, new_password: passwordForm.next }),
    onSuccess: () => {
      setPasswordMessage("密码已更新。下次登录请使用新密码。");
      setPasswordForm({ current: "", next: "", confirm: "" });
    },
  });

  const createMutation = useMutation({
    mutationFn: api.createAgencyPortalOrder,
    onSuccess: () => {
      setForm(emptyOrder);
      queryClient.invalidateQueries({ queryKey: ["agency-portal-orders"] });
    },
  });

  const withdrawMutation = useMutation({
    mutationFn: api.withdrawAgencyPortalOrder,
    onSuccess: async (result) => {
      setRequestMessage(result.result.mode === "direct_withdraw" ? "已从订单大厅撤回，订单回到未派状态。" : "当前订单无需撤回。");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["agency-portal-orders"] }),
        queryClient.invalidateQueries({ queryKey: ["agency-portal-change-requests"] }),
      ]);
    },
  });

  const changeRequestMutation = useMutation({
    mutationFn: ({ orderId, payload }: { orderId: number; payload: { request_type: "modify" | "cancel"; reason?: string; force?: boolean; changes?: Partial<Order> } }) =>
      api.createAgencyPortalChangeRequest(orderId, payload),
    onSuccess: async () => {
      setRequestMessage("已提交给车公司确认。");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["agency-portal-orders"] }),
        queryClient.invalidateQueries({ queryKey: ["agency-portal-change-requests"] }),
      ]);
    },
  });

  const publishAuctionMutation = useMutation({
    mutationFn: ({ orderId, payload }: { orderId: number; payload: { start_price_jpy: number; buyout_price_jpy: number; auction_duration_hours: 1 | 2 | 4; note?: string } }) =>
      api.publishAgencyPortalOrderToAuction(orderId, payload),
    onSuccess: async (result) => {
      setAuctionMessage(`已发布 ${result.count || 0} 单到订单大厅。`);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["agency-portal-orders"] }),
        queryClient.invalidateQueries({ queryKey: ["agency-portal-auction-listings"] }),
      ]);
    },
  });

  const uploadPdfMutation = useMutation({
    mutationFn: ({ orderId, file }: { orderId: number; file: File }) =>
      fileToDataUrl(file, true).then((file_base64) => api.uploadAgencyOrderItineraryPdf(orderId, { file_name: file.name, file_base64 })),
    onSuccess: async (result) => {
      setItineraryMessage(`已上传行程 PDF：${result.file_name}`);
      await queryClient.invalidateQueries({ queryKey: ["agency-portal-orders"] });
    },
  });

  const updateFlightMutation = useMutation({
    mutationFn: ({ orderId, payload }: { orderId: number; payload: Partial<Order> & { lookup?: boolean; query?: boolean } }) =>
      api.updateAgencyOrderFlightInfo(orderId, payload),
    onSuccess: async () => {
      setItineraryMessage("已更新航班信息。");
      await queryClient.invalidateQueries({ queryKey: ["agency-portal-orders"] });
    },
  });

  const uploadPaymentReceiptMutation = useMutation({
    mutationFn: ({ orderId, file }: { orderId: number; file: File }) =>
      fileToDataUrl(file).then((file_base64) => api.uploadAgencyPaymentReceipt(orderId, { file_name: file.name, file_base64 })),
    onSuccess: async (result) => {
      setSettlementMessage(`已上传付款回执：${result.file_name}，等待车公司确认收款。`);
      await queryClient.invalidateQueries({ queryKey: ["agency-portal-orders"] });
    },
  });

  const loggedIn = hasToken || Boolean(agency);

  async function submitBatch(parsedDrafts?: BatchOrderDraft[], publish?: PublishDraftSettings) {
    setBatchMessage("");
    const drafts = parsedDrafts?.length ? parsedDrafts : parseBatchOrders(batchText);
    if (!drafts.length) {
      setBatchMessage("没有可导入的订单。请按模板每行填写一单。");
      return;
    }
    for (const draft of drafts) {
      const created = await api.createAgencyPortalOrder(draft);
      if (created.order?.id && draft.itinerary_pdf_file) {
        const file_base64 = await fileToDataUrl(draft.itinerary_pdf_file, true);
        await api.uploadAgencyOrderItineraryPdf(created.order.id, { file_name: draft.itinerary_pdf_file.name, file_base64 });
      }
      if (publish && created.order?.id) {
        await api.publishAgencyPortalOrderToAuction(created.order.id, {
          start_price_jpy: Number(publish.startPrice || draft.price_jpy || draft.price || 0),
          buyout_price_jpy: Number(publish.buyoutPrice || draft.price_jpy || draft.price || 0),
          auction_duration_hours: publish.duration,
          note: publish.note,
        });
      }
    }
    await queryClient.invalidateQueries({ queryKey: ["agency-portal-orders"] });
    setBatchMessage(publish ? `已保存并发布 ${drafts.length} 单。` : `已保存 ${drafts.length} 单，可到订单列表继续发布。`);
    setActiveTab("orders");
  }

  return (
    <div className="min-h-screen bg-slate-100 px-4 py-6 2xl:px-8">
      <div className="mx-auto w-full max-w-none space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-slate-500">旅行社后台 Web</p>
            <h1 className="mt-1 text-3xl font-bold text-slate-950">旅行社运营后台</h1>
          </div>
          {loggedIn ? (
            <Button
              variant="secondary"
              onClick={() => {
                clearAgencyToken();
                setAgency(null);
                setPortalCode("");
                setPortalPassword("");
                queryClient.removeQueries({ queryKey: ["agency-portal-orders"] });
              }}
            >
              退出门户
            </Button>
          ) : null}
        </div>

        {!loggedIn ? (
          <Card className="mx-auto max-w-xl">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-700">
                  <Building2 size={20} />
                </div>
                <div>
                  <h2 className="text-base font-bold text-slate-950">旅行社登录</h2>
                  <p className="text-sm text-slate-500">输入登录代码识别旅行社，然后输入密码。</p>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <input className="h-10 w-full rounded-md border border-border px-3 text-sm" placeholder="登录代码，例如 AGA2026 / S1001" value={portalCode} onChange={(event) => setPortalCode(event.target.value)} />
              <div className="min-h-6 rounded-md bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-600">
                {resolvedAgency.isFetching ? "正在识别旅行社..." : resolvedAgency.data?.agency?.name ? `识别结果：${resolvedAgency.data.agency.name}` : portalCode.trim().length >= 2 ? "未找到该登录代码" : "请输入旅行社登录代码"}
              </div>
              <input className="h-10 w-full rounded-md border border-border px-3 text-sm" type="password" placeholder="登录密码" value={portalPassword} onChange={(event) => setPortalPassword(event.target.value)} />
              {loginMutation.isError ? <div className="text-sm font-semibold text-red-600">{loginMutation.error.message}</div> : null}
              <Button className="w-full" disabled={!portalCode.trim() || !portalPassword || loginMutation.isPending} onClick={() => loginMutation.mutate()}>
                登录旅行社门户
              </Button>
            </CardContent>
          </Card>
        ) : (
          <>
            <section className="grid gap-3 md:grid-cols-4">
              <Kpi title="全部订单" value={stats.total} />
              <Kpi title="待派/待发布" value={stats.unassigned} />
              <Kpi title="已接单/已派" value={stats.claimed} />
              <Kpi title="待结算" value={stats.pendingSettlement} />
            </section>

            <div className="flex flex-wrap gap-2 rounded-lg border border-border bg-white p-2">
              <TabButton active={activeTab === "single"} icon={<Send size={16} />} label="单条录入" onClick={() => setActiveTab("single")} />
              <TabButton active={activeTab === "batch"} icon={<Table2 size={16} />} label="批量录入" onClick={() => setActiveTab("batch")} />
              <TabButton active={activeTab === "orders"} icon={<ListChecks size={16} />} label="订单列表" onClick={() => setActiveTab("orders")} />
              <TabButton active={activeTab === "hall"} icon={<Gavel size={16} />} label="订单大厅" onClick={() => setActiveTab("hall")} />
              <TabButton active={activeTab === "mine"} icon={<UserRound size={16} />} label="我的订单" onClick={() => setActiveTab("mine")} />
              <TabButton active={activeTab === "calendar"} icon={<CalendarDays size={16} />} label="日历" onClick={() => setActiveTab("calendar")} />
              <TabButton active={activeTab === "settings"} icon={<Settings size={16} />} label="设置" onClick={() => setActiveTab("settings")} />
            </div>

            {activeTab === "single" ? (
              <SingleOrderPanel agency={agency} form={form} setForm={setForm} createMutation={createMutation} />
            ) : null}

            {activeTab === "batch" ? (
              <BatchPanel mode="mixed" batchText={batchText} setBatchText={setBatchText} batchMessage={batchMessage} onSubmit={submitBatch} />
            ) : null}

            {activeTab === "orders" ? (
              <TrackingPanel rows={trackingRows} keyword={trackingKeyword} setKeyword={setTrackingKeyword} uploadPdfMutation={uploadPdfMutation} updateFlightMutation={updateFlightMutation} publishMutation={publishAuctionMutation} message={itineraryMessage || auctionMessage} />
            ) : null}

            {activeTab === "hall" ? (
              <AgencyAuctionHallPanel
                rows={orderRows}
                listings={auctionListings.data || []}
                message={auctionMessage}
                requestMessage={requestMessage}
                settlementMessage={settlementMessage}
                changeRequests={changeRequests.data || []}
                publishMutation={publishAuctionMutation}
                withdrawMutation={withdrawMutation}
                changeRequestMutation={changeRequestMutation}
                uploadPaymentReceiptMutation={uploadPaymentReceiptMutation}
                fixedView="public"
              />
            ) : null}

            {activeTab === "mine" ? (
              <AgencyAuctionHallPanel
                rows={orderRows}
                listings={auctionListings.data || []}
                message={auctionMessage}
                requestMessage={requestMessage}
                settlementMessage={settlementMessage}
                changeRequests={changeRequests.data || []}
                publishMutation={publishAuctionMutation}
                withdrawMutation={withdrawMutation}
                changeRequestMutation={changeRequestMutation}
                uploadPaymentReceiptMutation={uploadPaymentReceiptMutation}
                fixedView="mine"
              />
            ) : null}

            {activeTab === "calendar" ? (
              <CalendarPanel date={calendarDate} setDate={setCalendarDate} rows={calendarRows} allRows={orderRows} publishMutation={publishAuctionMutation} />
            ) : null}

            {activeTab === "settings" ? (
              <AgencySettingsPanel
                agency={agency}
                form={passwordForm}
                setForm={setPasswordForm}
                message={passwordMessage}
                mutation={changePasswordMutation}
              />
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}

function AgencySettingsPanel({
  agency,
  form,
  setForm,
  message,
  mutation,
}: {
  agency: AgencyPortalAgency | null;
  form: { current: string; next: string; confirm: string };
  setForm: (form: { current: string; next: string; confirm: string }) => void;
  message: string;
  mutation: ReturnType<typeof useMutation<{ success: boolean }, Error, void>>;
}) {
  const mismatch = Boolean(form.next && form.confirm && form.next !== form.confirm);
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <KeyRound size={18} />
          <div>
            <h2 className="text-base font-bold text-slate-950">门户密码设置</h2>
            <p className="mt-1 text-sm text-slate-500">{agency?.name || "旅行社"} 可在这里修改门户登录密码。</p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="max-w-xl space-y-3">
        <input className="h-10 w-full rounded-md border border-border px-3 text-sm" type="password" placeholder="当前密码" value={form.current} onChange={(event) => setForm({ ...form, current: event.target.value })} />
        <input className="h-10 w-full rounded-md border border-border px-3 text-sm" type="password" placeholder="新密码，至少 6 位" value={form.next} onChange={(event) => setForm({ ...form, next: event.target.value })} />
        <input className="h-10 w-full rounded-md border border-border px-3 text-sm" type="password" placeholder="再次输入新密码" value={form.confirm} onChange={(event) => setForm({ ...form, confirm: event.target.value })} />
        {mismatch ? <div className="text-sm font-semibold text-red-600">两次输入的新密码不一致。</div> : null}
        {mutation.isError ? <div className="text-sm font-semibold text-red-600">{mutation.error.message}</div> : null}
        {message ? <div className="text-sm font-semibold text-emerald-700">{message}</div> : null}
        <Button disabled={!form.current || form.next.length < 6 || mismatch || mutation.isPending} onClick={() => mutation.mutate()}>
          修改密码
        </Button>
      </CardContent>
    </Card>
  );
}

function AirportEntryPanel({ batchText, setBatchText, batchMessage, onSubmit }: { batchText: string; setBatchText: (value: string) => void; batchMessage: string; onSubmit: (drafts?: BatchOrderDraft[], publish?: PublishDraftSettings) => void }) {
  return (
    <BatchPanel
      mode="airport"
      batchText={batchText}
      setBatchText={setBatchText}
      batchMessage={batchMessage}
      onSubmit={onSubmit}
    />
  );
}

function CharterEntryPanel({
  agency,
  form,
  setForm,
  createMutation,
  batchText,
  setBatchText,
  batchMessage,
  onSubmit,
}: {
  agency: AgencyPortalAgency | null;
  form: Partial<Order>;
  setForm: (form: Partial<Order>) => void;
  createMutation: ReturnType<typeof useMutation<{ order: Order }, Error, Partial<Order>>>;
  batchText: string;
  setBatchText: (value: string) => void;
  batchMessage: string;
  onSubmit: (drafts?: BatchOrderDraft[], publish?: PublishDraftSettings) => void;
}) {
  return (
    <section className="space-y-6">
      <SingleOrderPanel agency={agency} form={form} setForm={setForm} createMutation={createMutation} />
      <BatchPanel
        mode="charter"
        batchText={batchText}
        setBatchText={setBatchText}
        batchMessage={batchMessage}
        onSubmit={onSubmit}
      />
    </section>
  );
}

function SingleOrderPanel({ agency, form, setForm, createMutation }: { agency: AgencyPortalAgency | null; form: Partial<Order>; setForm: (form: Partial<Order>) => void; createMutation: ReturnType<typeof useMutation<{ order: Order }, Error, Partial<Order>>> }) {
  const queryClient = useQueryClient();
  const [charterText, setCharterText] = useState(charterTemplate);
  const [parseMessage, setParseMessage] = useState("");
  const [parseError, setParseError] = useState("");
  const [publishSettings, setPublishSettings] = useState<PublishDraftSettings>({ startPrice: "", buyoutPrice: "", duration: 2, note: "" });
  const [publishMessage, setPublishMessage] = useState("");
  const saveAndPublishMutation = useMutation({
    mutationFn: async () => {
      validateDraftBeforePublish(form);
      const created = await api.createAgencyPortalOrder(form);
      await api.publishAgencyPortalOrderToAuction(created.order.id, {
        start_price_jpy: Number(publishSettings.startPrice || form.price_jpy || form.price || 0),
        buyout_price_jpy: Number(publishSettings.buyoutPrice || form.price_jpy || form.price || 0),
        auction_duration_hours: publishSettings.duration,
        note: publishSettings.note,
      });
      return created;
    },
    onSuccess: async () => {
      setPublishMessage("订单已保存并发布到订单大厅。");
      await queryClient.invalidateQueries({ queryKey: ["agency-portal-orders"] });
    },
  });

  async function parseCharter() {
    setParseMessage("");
    setParseError("");
    try {
      const result = await api.parseAgencyPortalOrders(charterText, "charter", false);
      const parsed = result.orders[0];
      if (!parsed) {
        setParseError("没有解析出可填入的包车订单。");
        return;
      }
      const corrected = parseAgencyFreeformText(charterText, "包车");
      setForm({ ...form, ...parsed, ...corrected, order_type: "包车", flight_number: "", flight_status: "" });
      setPublishSettings((settings) => ({
        ...settings,
        startPrice: String(corrected.price_jpy || corrected.price || parsed.price_jpy || parsed.price || settings.startPrice || ""),
        buyoutPrice: String(corrected.price_jpy || corrected.price || parsed.price_jpy || parsed.price || settings.buyoutPrice || ""),
      }));
      setParseMessage("已解析并填入下方表单。");
    } catch (error) {
      setParseError(error instanceof Error ? error.message : "解析失败");
    }
  }

  return (
    <Card>
      <CardHeader>
            <h2 className="text-base font-bold text-slate-950">包车录入：单条解析</h2>
            <p className="mt-1 text-sm text-slate-500">{agency?.name || "旅行社"} 可先解析包车文本，确认字段、PDF 和价格后发布到订单大厅。</p>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="rounded-lg border border-border bg-slate-50 p-3">
          <div className="mb-2 text-sm font-bold text-slate-950">包车文本解析</div>
          <textarea className="min-h-36 w-full rounded-md border border-border px-3 py-2 text-sm" value={charterText} onChange={(event) => setCharterText(event.target.value)} />
          <Button className="mt-2" variant="secondary" onClick={parseCharter}>
            <FilePenLine size={16} />
            解析包车并填表
          </Button>
          {parseMessage ? <div className="mt-2 rounded-md bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700">{parseMessage}</div> : null}
          {parseError ? <div className="mt-2 text-sm font-semibold text-red-600">{parseError}</div> : null}
        </div>
        <div className="grid gap-2 md:grid-cols-4">
          <Field label="开始日期" type="date" value={form.order_date} onChange={(value) => setForm({ ...form, order_date: value, end_date: form.end_date || value })} />
          <Field label="结束日期" type="date" value={form.end_date} onChange={(value) => setForm({ ...form, end_date: value })} />
          <Field label="开始时间" type="time" value={form.start_time} onChange={(value) => setForm({ ...form, start_time: value })} />
          <Field label="结束时间" type="time" value={form.end_time} onChange={(value) => setForm({ ...form, end_time: value })} />
        </div>
        <div className="grid gap-2 md:grid-cols-2">
          <Field label="起点" value={form.pickup_location} onChange={(value) => setForm({ ...form, pickup_location: value })} />
          <Field label="终点" value={form.dropoff_location} onChange={(value) => setForm({ ...form, dropoff_location: value })} />
        </div>
        <div className="grid gap-2 md:grid-cols-6">
          <OrderTypeSelect label="类型" value={form.order_type} onChange={(value) => setForm({ ...form, order_type: value, end_time: addHours(form.start_time || "09:00", value === "包车" ? 10 : 2) })} />
          <Field label="车型" value={form.vehicle_type} onChange={(value) => setForm({ ...form, vehicle_type: value })} />
          <Field label="人数" type="number" value={form.passenger_count} onChange={(value) => setForm({ ...form, passenger_count: Number(value || 0) })} />
          <Field label="报价 JPY" type="number" value={form.price} onChange={(value) => setForm({ ...form, price: value ? Number(value) : undefined })} />
          <Field label="客人姓名" value={form.guest_name} onChange={(value) => setForm({ ...form, guest_name: value })} />
          <Field label="联系方式" value={form.guest_contact} onChange={(value) => setForm({ ...form, guest_contact: value })} />
        </div>
        <div className="grid gap-2 md:grid-cols-5">
          <Field label="导游姓名" value={form.guide_name} onChange={(value) => setForm({ ...form, guide_name: value })} />
          <Field label="导游电话" value={form.guide_phone} onChange={(value) => setForm({ ...form, guide_phone: value })} />
          <Field label="导游微信" value={form.guide_wechat} onChange={(value) => setForm({ ...form, guide_wechat: value })} />
          <Field label="导游 Line" value={form.guide_line} onChange={(value) => setForm({ ...form, guide_line: value })} />
          <Field label="导游 WhatsApp" value={form.guide_whatsapp} onChange={(value) => setForm({ ...form, guide_whatsapp: value })} />
        </div>
        <textarea className="min-h-24 w-full rounded-md border border-border px-3 py-2 text-sm" placeholder="备注 / 费用说明" value={form.fee_remark || form.remark || ""} onChange={(event) => setForm({ ...form, fee_remark: event.target.value, remark: event.target.value })} />
        <PublishSettingsPanel draft={form} settings={publishSettings} setSettings={setPublishSettings} />
        {createMutation.isError ? <div className="text-sm font-semibold text-red-600">{createMutation.error.message}</div> : null}
        {saveAndPublishMutation.error instanceof Error ? <div className="text-sm font-semibold text-red-600">{saveAndPublishMutation.error.message}</div> : null}
        {publishMessage ? <div className="rounded-md bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700">{publishMessage}</div> : null}
        <div className="flex flex-wrap justify-end gap-2">
          <Button className="h-9 px-4" variant="secondary" disabled={createMutation.isPending} onClick={() => createMutation.mutate(form)}>
            保存为订单
          </Button>
          <Button className="h-9 px-4" disabled={saveAndPublishMutation.isPending} onClick={() => saveAndPublishMutation.mutate()}>
            <Send size={16} />
            保存并发布到大厅
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function BatchPanel({
  mode = "mixed",
  batchText,
  setBatchText,
  batchMessage,
  onSubmit,
}: {
  mode?: "airport" | "charter" | "mixed";
  batchText: string;
  setBatchText: (value: string) => void;
  batchMessage: string;
  onSubmit: (drafts?: BatchOrderDraft[], publish?: PublishDraftSettings) => void;
}) {
  const [parsedRows, setParsedRows] = useState<BatchOrderDraft[]>([]);
  const [parseMessage, setParseMessage] = useState("");
  const [parseError, setParseError] = useState("");
  const [draftError, setDraftError] = useState("");
  const [publishSettings, setPublishSettings] = useState<PublishDraftSettings>({ startPrice: "", buyoutPrice: "", duration: 2, note: "" });
  const preview = parsedRows.length ? parsedRows : parseBatchOrders(batchText);
  const isAirportMode = mode === "airport";
  const isCharterMode = mode === "charter";
  const updateDraft = (index: number, patch: BatchOrderDraft) => setParsedRows((rows) => {
    const baseRows = rows.length ? rows : parseBatchOrders(batchText);
    return baseRows.map((row, rowIndex) => (rowIndex === index ? { ...row, ...patch } : row));
  });

  async function parseAirportBatch() {
    setParseMessage("");
    setParseError("");
    try {
      const result = await api.parseAgencyPortalOrders(batchText, "airport_batch", true);
      setParsedRows(mergeParsedRowsWithSource(result.orders, batchText, "接机"));
      setParseMessage(`已解析 ${result.count || result.orders.length} 条机场接送订单。`);
    } catch (error) {
      setParseError(error instanceof Error ? error.message : "解析失败");
    }
  }

  async function parseCharterBatch() {
    setParseMessage("");
    setParseError("");
    try {
      const result = await api.parseAgencyPortalOrders(batchText, "charter_batch", true);
      setParsedRows(mergeParsedRowsWithSource(result.orders, batchText, "包车"));
      setParseMessage(`已解析 ${result.count || result.orders.length} 条包车订单。`);
    } catch (error) {
      setParseError(error instanceof Error ? error.message : "解析失败");
    }
  }

  function parseMixedBatch() {
    setParseMessage("");
    setParseError("");
    const rows = parseBatchOrders(batchText);
    setParsedRows(rows);
    setParseMessage(`已自动解析 ${rows.length} 条订单，包含机场接送和包车。请在右侧表格确认类型、价格和 PDF。`);
  }

  return (
    <section className="space-y-5">
      <Card>
        <CardHeader>
          <h2 className="text-base font-bold text-slate-950">{isAirportMode ? "机场接送录入" : isCharterMode ? "包车录入：批量解析" : "批量录入"}</h2>
          <p className="mt-1 text-sm text-slate-500">
            {isAirportMode
              ? "机场接送支持批量解析，确认接机/送机、日期、时间、起终点、人数、行李数和价格后发布。"
              : isCharterMode
                ? "包车支持单条或多条解析，每条订单确认字段后可保存，再在订单列表上传标准 PDF 或发布。"
                : "机场接送和包车都支持一行一单自动解析，确认预览后批量导入；包车行可上传 PDF。"}
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <textarea
            className="min-h-56 w-full rounded-md border border-border px-3 py-2 font-mono text-sm leading-6"
            value={batchText}
            onChange={(event) => {
              setBatchText(event.target.value);
              setParsedRows([]);
              setParseMessage("");
              setParseError("");
            }}
          />
          <div className="flex flex-wrap gap-2">
            {mode === "mixed" ? (
              <Button variant="secondary" disabled={!batchText.trim()} onClick={parseMixedBatch}>
                <FilePenLine size={16} />
                自动解析
              </Button>
            ) : null}
            {!isCharterMode && mode !== "mixed" ? (
              <Button variant="secondary" disabled={!batchText.trim()} onClick={parseAirportBatch}>
                <FilePenLine size={16} />
                解析机场接送
              </Button>
            ) : null}
            {!isAirportMode && mode !== "mixed" ? (
              <Button variant="secondary" disabled={!batchText.trim()} onClick={parseCharterBatch}>
                <FilePenLine size={16} />
                解析包车批量
              </Button>
            ) : null}
            {mode === "mixed" ? (
              <Button variant="secondary" onClick={() => setBatchText(batchTemplate)}>
                填入机场接送示例
              </Button>
            ) : null}
            {isCharterMode || mode === "mixed" ? (
              <Button variant="secondary" onClick={() => setBatchText(charterBatchTemplate)}>
                填入包车示例
              </Button>
            ) : null}
          </div>
          {parseMessage ? <div className="rounded-md bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700">{parseMessage}</div> : null}
          {parseError ? <div className="text-sm font-semibold text-red-600">{parseError}</div> : null}
          {batchMessage ? <div className="rounded-md bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700">{batchMessage}</div> : null}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <h2 className="text-base font-bold text-slate-950">可编辑表格</h2>
          <p className="mt-1 text-sm text-slate-500">解析后先修改表格，再填写起拍价、一口价和拍卖时间。</p>
        </CardHeader>
        <CardContent className="p-0">
          <BatchEditablePreview rows={preview} updateDraft={updateDraft} />
          <div className="border-t border-border p-4">
            <PublishSettingsPanel draft={preview[0] || {}} settings={publishSettings} setSettings={setPublishSettings} />
            {draftError ? <div className="mt-2 text-sm font-semibold text-red-600">{draftError}</div> : null}
            <div className="mt-3 grid gap-2 md:grid-cols-2">
              <Button disabled={!preview.length} onClick={() => {
                setDraftError("");
                onSubmit(preview);
              }}>保存为订单</Button>
              <Button disabled={!preview.length} onClick={() => {
                setDraftError("");
                if (!confirmBatchPublish(preview)) return;
                onSubmit(preview, publishSettings);
              }}>保存并发布到大厅</Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </section>
  );
}

function BatchEditablePreview({ rows, updateDraft }: { rows: BatchOrderDraft[]; updateDraft: (index: number, patch: BatchOrderDraft) => void }) {
  if (!rows.length) {
    return <div className="py-10 text-center text-sm text-slate-500">解析后会在这里显示可修改的订单草稿。</div>;
  }
  const showPdfColumn = rows.some((row) => isCharterOrder(row as Order));
  return (
    <div className="overflow-x-auto">
      <table className={`data-table ${showPdfColumn ? "min-w-[1160px]" : "min-w-[1040px]"}`}>
        <thead>
          <tr>
            <th>日期</th>
            <th>开始</th>
            <th>结束</th>
            <th>类型</th>
            {showPdfColumn ? <th>PDF</th> : null}
            <th>起点</th>
            <th>终点</th>
            <th>车型</th>
            <th>人数</th>
            <th>行李数</th>
            <th>客人</th>
            <th>电话</th>
            <th>报价</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${row.order_date}-${row.start_time}-${index}`}>
              <td><MiniInput type="date" value={row.order_date} onChange={(value) => updateDraft(index, { order_date: value, end_date: row.end_date || value })} /></td>
              <td><MiniInput type="time" value={row.start_time} onChange={(value) => updateDraft(index, { start_time: value })} /></td>
              <td><MiniInput type="time" value={row.end_time} onChange={(value) => updateDraft(index, { end_time: value })} /></td>
              <td><MiniOrderTypeSelect value={row.order_type} onChange={(value) => updateDraft(index, { order_type: value, end_time: addHours(row.start_time || "09:00", value === "包车" ? 10 : 2) })} /></td>
              {showPdfColumn ? (
                <td>
                  {isCharterOrder(row as Order) ? (
                    <label className="inline-flex h-8 min-w-28 cursor-pointer items-center justify-center rounded-md border border-blue-200 bg-blue-50 px-2 text-xs font-bold text-blue-700">
                      {row.itinerary_pdf_name || "上传PDF"}
                      <input
                        className="sr-only"
                        type="file"
                        accept="application/pdf,.pdf"
                        onChange={(event) => {
                          const file = event.target.files?.[0];
                          updateDraft(index, { itinerary_pdf_file: file, itinerary_pdf_name: file?.name || row.itinerary_pdf_name });
                          event.currentTarget.value = "";
                        }}
                      />
                    </label>
                  ) : (
                    <span className="text-xs font-semibold text-slate-400">接送机无PDF</span>
                  )}
                </td>
              ) : null}
              <td><MiniInput value={row.pickup_location} onChange={(value) => updateDraft(index, { pickup_location: value })} /></td>
              <td><MiniInput value={row.dropoff_location} onChange={(value) => updateDraft(index, { dropoff_location: value })} /></td>
              <td><MiniInput value={row.vehicle_type} onChange={(value) => updateDraft(index, { vehicle_type: value })} /></td>
              <td><MiniInput type="number" value={row.passenger_count} onChange={(value) => updateDraft(index, { passenger_count: Number(value || 0) })} /></td>
              <td><MiniInput type="number" value={row.luggage_count} onChange={(value) => updateDraft(index, { luggage_count: Number(value || 0) })} /></td>
              <td><MiniInput value={row.guest_name} onChange={(value) => updateDraft(index, { guest_name: value })} /></td>
              <td><MiniInput value={row.guest_contact} onChange={(value) => updateDraft(index, { guest_contact: value })} /></td>
              <td><MiniInput type="number" value={row.price_jpy || row.price} onChange={(value) => updateDraft(index, { price: value ? Number(value) : undefined, price_jpy: value ? Number(value) : undefined })} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="border-t border-border px-4 py-2 text-xs font-semibold text-slate-500">
        解析结果只是草稿。请先逐列确认，尤其是订单类型、起终点、客人姓名、电话、车型、人数、行李数和报价。机场接送批量订单不需要 PDF；只有包车订单需要标准行程 PDF。
      </div>
    </div>
  );
}

function PublishSettingsPanel({ draft, settings, setSettings }: { draft: Partial<Order>; settings: PublishDraftSettings; setSettings: (settings: PublishDraftSettings) => void }) {
  const isAirport = isAirportTransfer(draft);
  return (
    <div className="rounded-lg border border-border bg-slate-50 p-3">
      <div className="text-sm font-bold text-slate-950">发布设置</div>
      <div className="mt-1 text-xs font-semibold text-slate-500">
        {isAirport ? "机场接送不需要上传标准 PDF。" : "包车订单可在订单保存后上传标准行程 PDF，再发布或重新发布。"}
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-4">
        <Field label="起拍价 JPY" type="number" value={settings.startPrice || draft.price_jpy || draft.price || ""} onChange={(value) => setSettings({ ...settings, startPrice: value })} />
        <Field label="一口价 JPY" type="number" value={settings.buyoutPrice || draft.price_jpy || draft.price || ""} onChange={(value) => setSettings({ ...settings, buyoutPrice: value })} />
        <label className="block text-sm">
          <span className="mb-1 block font-semibold text-slate-700">拍卖时间</span>
          <select className="h-10 w-full rounded-md border border-border px-3 text-sm" value={settings.duration} onChange={(event) => setSettings({ ...settings, duration: Number(event.target.value) as 1 | 2 | 4 })}>
            <option value={1}>1 小时</option>
            <option value={2}>2 小时</option>
            <option value={4}>4 小时</option>
          </select>
        </label>
        <Field label="发布备注" value={settings.note || ""} onChange={(value) => setSettings({ ...settings, note: value })} />
      </div>
    </div>
  );
}

function MiniInput({ value, onChange, type = "text" }: { value: unknown; onChange: (value: string) => void; type?: string }) {
  return <input className="h-8 w-full min-w-24 rounded-md border border-border px-2 text-xs" type={type} value={String(value ?? "")} onChange={(event) => onChange(event.target.value)} />;
}

function MiniOrderTypeSelect({ value, onChange }: { value: unknown; onChange: (value: AgencyOrderKind) => void }) {
  return (
    <select className="h-8 w-full min-w-24 rounded-md border border-border px-2 text-xs" value={toAgencyOrderKind(value)} onChange={(event) => onChange(event.target.value as AgencyOrderKind)}>
      <option value="包车">包车</option>
      <option value="接机">接机</option>
      <option value="送机">送机</option>
    </select>
  );
}

function validateDraftBeforePublish(draft: Partial<Order>) {
  const missing: string[] = [];
  if (!draft.order_date) missing.push("日期");
  if (!draft.start_time) missing.push("时间");
  if (!draft.pickup_location) missing.push("起点");
  if (!draft.dropoff_location) missing.push("终点");
  if (!draft.vehicle_type) missing.push("车型");
  if (!draft.guest_name) missing.push("客人姓名");
  if (!draft.guest_contact) missing.push("客人电话");
  if (!Number(draft.price_jpy || draft.price || 0)) missing.push("报价");
  if (missing.length) throw new Error(`发布前请补全：${missing.join("、")}`);
}

function draftMissingFields(draft: Partial<Order>) {
  const missing: string[] = [];
  if (!draft.order_date) missing.push("日期");
  if (!draft.start_time) missing.push("时间");
  if (!draft.pickup_location) missing.push("起点");
  if (!draft.dropoff_location) missing.push("终点");
  if (!draft.vehicle_type) missing.push("车型");
  if (!draft.passenger_count) missing.push("人数");
  if (!draft.guest_name) missing.push("客人姓名");
  if (!draft.guest_contact) missing.push("客人电话");
  if (!Number(draft.price_jpy || draft.price || 0)) missing.push("报价");
  return missing;
}

function confirmBatchPublish(rows: Partial<Order>[]) {
  const issues = rows
    .map((row, index) => ({ index: index + 1, missing: draftMissingFields(row) }))
    .filter((item) => item.missing.length);
  if (!issues.length) return true;
  const summary = issues
    .slice(0, 8)
    .map((item) => `第 ${item.index} 行缺少：${item.missing.join("、")}`)
    .join("\n");
  const more = issues.length > 8 ? `\n还有 ${issues.length - 8} 行也有缺项。` : "";
  return window.confirm(
    `解析表格中仍有缺项。\n\n${summary}${more}\n\n确认发布后，订单大厅会先展示已有的基础信息；接单后车公司看到的完整订单也可能缺少这些字段。是否仍然发布？`,
  );
}

function TrackingPanel({
  rows,
  keyword,
  setKeyword,
  uploadPdfMutation,
  updateFlightMutation,
  publishMutation,
  message,
}: {
  rows: Order[];
  keyword: string;
  setKeyword: (value: string) => void;
  uploadPdfMutation: UploadPdfMutation;
  updateFlightMutation: UpdateFlightMutation;
  publishMutation: PublishAuctionMutation;
  message: string;
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-slate-950">订单列表</h2>
            <p className="mt-1 text-sm text-slate-500">内部草稿和全量订单管理：未发布、已发布、竞拍中、落拍未开始、已开始、未结算、已结算。历史订单按日期搜索查看。</p>
          </div>
          <input className="h-9 w-72 rounded-md border border-border px-3 text-sm" value={keyword} onChange={(event) => setKeyword(event.target.value)} placeholder="搜索订单号 / 路线 / 客人 / 状态" />
        </div>
      </CardHeader>
      <CardContent className="overflow-x-auto p-0">
        {message ? <div className="mx-4 mb-3 rounded-md bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700">{message}</div> : null}
        {uploadPdfMutation.error instanceof Error ? <div className="mx-4 mb-3 text-sm font-semibold text-red-600">{uploadPdfMutation.error.message}</div> : null}
        {updateFlightMutation.error instanceof Error ? <div className="mx-4 mb-3 text-sm font-semibold text-red-600">{updateFlightMutation.error.message}</div> : null}
        <OrderTable rows={rows} uploadPdfMutation={uploadPdfMutation} updateFlightMutation={updateFlightMutation} publishMutation={publishMutation} />
      </CardContent>
    </Card>
  );
}

function AgencyAuctionHallPanel({
  rows,
  listings,
  message,
  requestMessage,
  settlementMessage,
  changeRequests,
  publishMutation,
  withdrawMutation,
  changeRequestMutation,
  uploadPaymentReceiptMutation,
  fixedView,
}: {
  rows: Order[];
  listings: AuctionListing[];
  message: string;
  requestMessage: string;
  settlementMessage: string;
  changeRequests: AgencyOrderChangeRequest[];
  publishMutation: PublishAuctionMutation;
  withdrawMutation: ReturnType<typeof useMutation<{ result: { success: boolean; mode: string; order_id: number; listing_id?: number } }, Error, number>>;
  changeRequestMutation: ReturnType<typeof useMutation<{ request: AgencyOrderChangeRequest }, Error, { orderId: number; payload: { request_type: "modify" | "cancel"; reason?: string; force?: boolean; changes?: Partial<Order> } }>>;
  uploadPaymentReceiptMutation: UploadReceiptMutation;
  fixedView?: HallSubView;
}) {
  const publishable = rows.filter((order) => ["unassigned", "auction_cancelled", "auction_expired"].includes(order.dispatch_status || "unassigned"));
  const airportListings = listings.filter(isAirportTransfer);
  const charterListings = listings.filter((item) => !isAirportTransfer(item));
  const [myStatusFilter, setMyStatusFilter] = useState("ongoing");
  const [hallViewState, setHallView] = useState<HallSubView>(fixedView || "public");
  const hallView = fixedView || hallViewState;
  const myHallRows = filterAgencyHallOrders(sortAgencyHallOrders(rows), myStatusFilter);
  const [orderId, setOrderId] = useState<number | "">(publishable[0]?.id || "");
  const selected = publishable.find((order) => order.id === Number(orderId));
  const [startPrice, setStartPrice] = useState("");
  const [buyoutPrice, setBuyoutPrice] = useState("");
  const [duration, setDuration] = useState<1 | 2 | 4>(1);
  const [note, setNote] = useState("");

  function submit() {
    if (!selected) return;
    publishMutation.mutate({
      orderId: selected.id,
      payload: {
        start_price_jpy: Number(startPrice || selected.price_jpy || selected.price || 0),
        buyout_price_jpy: Number(buyoutPrice || selected.price_jpy || selected.price || 0),
        auction_duration_hours: duration,
        note,
      },
    });
  }

  return (
    <section className="space-y-6">
      <div className="rounded-lg border border-border bg-white p-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-bold text-slate-950">{hallView === "mine" ? "我的订单" : "订单大厅"}</h2>
            <p className="mt-1 text-sm text-slate-500">
              {hallView === "mine" ? "查看我发布的订单、竞拍状态、撤回/变更申请和费用结算。" : "公开市场不展示订单号、旅行社身份和联系人，只展示接送时间、主要行程、车型和价格。"}
            </p>
          </div>
          {!fixedView ? (
            <div className="flex flex-wrap gap-2">
              <HallViewButton active={hallView === "public"} label="公开大厅" count={airportListings.length + charterListings.length} onClick={() => setHallView("public")} />
              <HallViewButton active={hallView === "mine"} label="我的订单" count={rows.length} onClick={() => setHallView("mine")} />
              <HallViewButton active={hallView === "publish"} label="发布订单" count={publishable.length} onClick={() => setHallView("publish")} />
            </div>
          ) : null}
        </div>
      </div>

      {hallView === "public" ? (
        <Card>
          <CardHeader>
            <h2 className="text-base font-bold text-slate-950">公开订单大厅</h2>
            <p className="mt-1 text-sm text-slate-500">这里是车公司可见的大厅列表，只展示日期、时间、主要行程、车型和价格，不展示联系人。</p>
          </CardHeader>
          <CardContent className="space-y-5 overflow-hidden">
            <HallListingTable title="机场接送" rows={airportListings} />
            <HallListingTable title="包车 / 复杂行程" rows={charterListings} />
          </CardContent>
        </Card>
      ) : null}

      {hallView === "mine" ? (
        <div className="space-y-5">
          <MyHallOrdersTable
            rows={myHallRows}
            allRows={rows}
            filter={myStatusFilter}
            setFilter={setMyStatusFilter}
            requests={changeRequests}
            message={requestMessage}
            publishMutation={publishMutation}
            withdrawMutation={withdrawMutation}
            changeRequestMutation={changeRequestMutation}
          />
          <AgencySettlementPanel rows={rows} message={settlementMessage} uploadPaymentReceiptMutation={uploadPaymentReceiptMutation} />
        </div>
      ) : null}

      {hallView === "publish" ? (
        <Card className="max-w-3xl">
          <CardHeader>
            <h2 className="text-base font-bold text-slate-950">发布到订单大厅</h2>
            <p className="mt-1 text-sm text-slate-500">选择未派、流拍或已撤回订单，设置起拍价、一口价和拍卖时间后发布。</p>
          </CardHeader>
          <CardContent className="space-y-3">
            <select className="h-10 w-full rounded-md border border-border px-3 text-sm" value={orderId} onChange={(event) => setOrderId(event.target.value ? Number(event.target.value) : "")}>
              <option value="">选择未派订单</option>
              {publishable.map((order) => (
                <option key={order.id} value={order.id}>{order.oid || order.id} / {order.order_date} {order.start_time || ""}{isRepublishableOrder(order) ? " / 可再发布" : ""}</option>
              ))}
            </select>
            {selected && isRepublishableOrder(selected) ? (
              <div className="rounded-md bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-700">
                原订单号保持不变；本次会生成新的大厅发布号。上次发布状态：{agencyAuctionStatusLabel(selected)}。
              </div>
            ) : null}
            <div className="grid gap-3 md:grid-cols-2">
              <Field label="起拍价 JPY" type="number" value={startPrice || selected?.price_jpy || selected?.price || ""} onChange={setStartPrice} />
              <Field label="一口价 JPY" type="number" value={buyoutPrice || selected?.price_jpy || selected?.price || ""} onChange={setBuyoutPrice} />
              <label className="block text-sm md:col-span-2">
                <span className="mb-1 block font-semibold text-slate-700">拍卖时间</span>
                <div className="flex gap-2">
                  {[1, 2, 4].map((hour) => (
                    <button key={hour} className={`h-9 rounded-md px-3 text-sm font-bold ${duration === hour ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600"}`} onClick={() => setDuration(hour as 1 | 2 | 4)}>
                      {hour} 小时
                    </button>
                  ))}
                </div>
              </label>
              <textarea className="min-h-20 rounded-md border border-border px-3 py-2 text-sm md:col-span-2" value={note} onChange={(event) => setNote(event.target.value)} placeholder="公开备注，只写服务要求，不写联系人" />
              <div className="rounded-md bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-500 md:col-span-2">
                标准行程 PDF 在“订单跟踪”的每个行程中维护；发布到大厅时只公开基础行程、车型和价格。
              </div>
            </div>
            <Button className="w-full" disabled={!selected || publishMutation.isPending} onClick={submit}>
              <Gavel size={16} />
              发布到大厅
            </Button>
            {message ? <div className="rounded-md bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700">{message}</div> : null}
            {publishMutation.error instanceof Error ? <div className="text-sm font-semibold text-red-600">{publishMutation.error.message}</div> : null}
          </CardContent>
        </Card>
      ) : null}
    </section>
  );
}

function MyHallOrdersTable({
  rows,
  allRows,
  filter,
  setFilter,
  requests,
  message,
  publishMutation,
  withdrawMutation,
  changeRequestMutation,
}: {
  rows: Order[];
  allRows: Order[];
  filter: string;
  setFilter: (value: string) => void;
  requests: AgencyOrderChangeRequest[];
  message: string;
  publishMutation: PublishAuctionMutation;
  withdrawMutation: ReturnType<typeof useMutation<{ result: { success: boolean; mode: string; order_id: number; listing_id?: number } }, Error, number>>;
  changeRequestMutation: ReturnType<typeof useMutation<{ request: AgencyOrderChangeRequest }, Error, { orderId: number; payload: { request_type: "modify" | "cancel"; reason?: string; force?: boolean; changes?: Partial<Order> } }>>;
}) {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selected = rows.find((order) => order.id === selectedId) || rows[0] || null;
  const [reason, setReason] = useState("");
  const [changes, setChanges] = useState<Partial<Order>>({});
  const publishing = allRows.filter((order) => ["listed", "bidding"].includes(order.auction_status || "") || order.dispatch_status === "auction_listed").length;
  const expired = allRows.filter((order) => order.auction_status === "expired" || order.dispatch_status === "auction_expired").length;
  const withdrawn = allRows.filter((order) => order.auction_status === "cancelled" || order.dispatch_status === "auction_cancelled").length;
  const claimed = allRows.filter((order) => order.auction_status === "claimed" || order.dispatch_status === "auction_claimed").length;
  const pendingPayment = allRows.filter((order) => ["payment_requested", "receipt_uploaded"].includes(order.settlement_status || order.agency_settlement_status || "")).length;
  const selectedRequests = selected ? requests.filter((item) => item.order_id === selected.id) : [];
  const canDirectWithdraw = Boolean(selected && (["listed", "bidding"].includes(selected.auction_status || "") || selected.dispatch_status === "auction_listed"));
  const selectedClosed = Boolean(selected && (["paid", "settled"].includes(selected.settlement_status || selected.agency_settlement_status || "") || ["completed", "cancelled"].includes(selected.execution_status || "")));
  const canRequestCarrierApproval = Boolean(selected && !canDirectWithdraw && !selectedClosed);

  function submitCancel(force = false) {
    if (!selected) return;
    changeRequestMutation.mutate({
      orderId: selected.id,
      payload: { request_type: "cancel", reason: reason || "订单大厅我的订单申请撤销", force },
    });
  }

  function submitModify() {
    if (!selected) return;
    const payload = Object.fromEntries(Object.entries(changes).filter(([, value]) => value !== undefined && value !== ""));
    if (!Object.keys(payload).length) return;
    changeRequestMutation.mutate({
      orderId: selected.id,
      payload: { request_type: "modify", reason: reason || "订单大厅我的订单申请修改", changes: payload },
    });
  }

  function quickPublish(order: Order) {
    const price = Number(order.price_jpy || order.price || order.auction_start_price_jpy || 0);
    publishMutation.mutate({
      orderId: order.id,
      payload: {
        start_price_jpy: price,
        buyout_price_jpy: price,
        auction_duration_hours: 2,
        note: "从我的订单快速发布",
      },
    });
  }

  function submitCancelFor(order: Order, force = false) {
    changeRequestMutation.mutate({
      orderId: order.id,
      payload: { request_type: "cancel", reason: reason || "订单大厅我的订单申请撤销", force },
    });
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-50 px-3 py-2">
        <div>
          <div className="text-sm font-bold text-slate-950">我的订单</div>
          <div className="mt-1 text-xs font-semibold text-slate-500">默认显示进行中订单；变更、撤回、结算都在这里处理。</div>
        </div>
        <div className="flex flex-wrap gap-2 text-xs font-semibold text-slate-500">
          <span>发布中 {publishing}</span>
          <span>已接单 {claimed}</span>
          <span>流拍 {expired}</span>
          <span>待结算 {pendingPayment}</span>
        </div>
      </div>
      <div className="flex flex-wrap gap-2 border-t border-border bg-white px-3 py-2 text-xs font-semibold text-slate-600">
        <span>超时撤回 {expired}</span>
        <span>已撤回 {withdrawn}</span>
      </div>
      <div className="flex flex-wrap gap-2 border-t border-border bg-white px-3 py-3">
        {[
          ["ongoing", "进行中"],
          ["all", "全部"],
          ["publishing", "发布中"],
          ["claimed", "已接单"],
          ["expired", "流拍"],
          ["pending_payment", "待结算"],
          ["completed", "已完成"],
        ].map(([value, label]) => (
          <button key={value} className={`h-8 rounded-md px-3 text-xs font-bold ${filter === value ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`} onClick={() => setFilter(value)}>
            {label}
          </button>
        ))}
        <button className={`h-8 rounded-md px-3 text-xs font-bold ${filter === "withdrawn" ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`} onClick={() => setFilter("withdrawn")}>
          已撤回
        </button>
      </div>
      {message ? <div className="mx-3 my-2 rounded-md bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700">{message}</div> : null}
      {withdrawMutation.error instanceof Error ? <div className="mx-3 my-2 text-sm font-semibold text-red-600">{withdrawMutation.error.message}</div> : null}
      {changeRequestMutation.error instanceof Error ? <div className="mx-3 my-2 text-sm font-semibold text-red-600">{changeRequestMutation.error.message}</div> : null}
      <div className="overflow-x-auto">
      <table className="data-table min-w-[1480px]">
        <thead>
          <tr>
            <th className="min-w-[230px] whitespace-nowrap">订单</th>
            <th className="min-w-[170px] whitespace-nowrap">日期时间</th>
            <th className="min-w-[440px] whitespace-nowrap">主要行程</th>
            <th className="min-w-[110px] whitespace-nowrap">状态</th>
            <th className="min-w-[150px] whitespace-nowrap">起拍/一口价</th>
            <th className="min-w-[150px] whitespace-nowrap">竞拍</th>
            <th className="min-w-[110px] whitespace-nowrap">结算</th>
            <th className="min-w-[140px] whitespace-nowrap">操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.length ? rows.map((order) => (
            <tr key={order.id} className={selected?.id === order.id ? "bg-blue-50/50" : ""}>
              <td className="whitespace-nowrap font-bold text-slate-950">
                {order.oid || order.id}
                <div className="mt-1 text-xs font-semibold text-slate-500">{order.auction_listing_code || "未发布"}</div>
              </td>
              <td className="whitespace-nowrap">{order.order_date} {order.start_time}-{order.end_time}</td>
              <td className="whitespace-nowrap">{order.pickup_location || "-"} {"->"} {order.dropoff_location || "-"}</td>
              <td className="whitespace-nowrap"><AgencyAuctionStatusBadge order={order} /></td>
              <td className="whitespace-nowrap">{order.auction_start_price_jpy || "-"} / {order.auction_buyout_price_jpy || "-"}</td>
              <td className="whitespace-nowrap">{order.auction_bid_count || 0} 次 / 当前 {order.auction_current_bid_jpy || "-"}</td>
              <td className="whitespace-nowrap"><StatusBadge status={order.settlement_status || order.agency_settlement_status} /></td>
              <td className="whitespace-nowrap">
                <div className="flex flex-nowrap gap-2">
                  {canPublishToHall(order) ? (
                    <Button className="h-8 px-2" disabled={publishMutation.isPending} onClick={() => quickPublish(order)}>发布</Button>
                  ) : null}
                  {["listed", "bidding"].includes(order.auction_status || "") || order.dispatch_status === "auction_listed" ? (
                    <Button className="h-8 px-2" variant="secondary" disabled={withdrawMutation.isPending} onClick={() => withdrawMutation.mutate(order.id)}>撤回</Button>
                  ) : null}
                  {!isClosedForAgencyAction(order) ? (
                    <Button className="h-8 px-2" variant="secondary" disabled={changeRequestMutation.isPending} onClick={() => submitCancelFor(order, false)}>申请撤销</Button>
                  ) : null}
                </div>
              </td>
            </tr>
          )) : <tr><td colSpan={8} className="py-8 text-center text-sm text-slate-500">暂无符合筛选的订单</td></tr>}
        </tbody>
      </table>
      </div>
      {false && selected ? (
        <div className="border-t border-border bg-white p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-sm font-bold text-slate-950">处理：{selected.oid || selected.id}</div>
              <div className="mt-1 text-xs font-semibold text-slate-500">{selected.pickup_location || "-"} {"->"} {selected.dropoff_location || "-"}</div>
            </div>
            {canDirectWithdraw ? <StatusBadge status="auction_listed" /> : <AgencyAuctionStatusBadge order={selected} />}
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <Field label="开始日期" type="date" value={changes.order_date ?? selected.order_date ?? ""} onChange={(value) => setChanges({ ...changes, order_date: value })} />
            <Field label="开始时间" type="time" value={changes.start_time ?? selected.start_time ?? ""} onChange={(value) => setChanges({ ...changes, start_time: value })} />
            <Field label="起点" value={changes.pickup_location ?? selected.pickup_location ?? ""} onChange={(value) => setChanges({ ...changes, pickup_location: value })} />
            <Field label="终点" value={changes.dropoff_location ?? selected.dropoff_location ?? ""} onChange={(value) => setChanges({ ...changes, dropoff_location: value })} />
            <Field label="车型" value={changes.vehicle_type ?? selected.vehicle_type ?? ""} onChange={(value) => setChanges({ ...changes, vehicle_type: value })} />
            <Field label="报价 JPY" type="number" value={changes.price ?? selected.price ?? ""} onChange={(value) => setChanges({ ...changes, price: value ? Number(value) : undefined, price_jpy: value ? Number(value) : undefined })} />
          </div>
          <textarea className="mt-3 min-h-20 w-full rounded-md border border-border px-3 py-2 text-sm" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="变更/撤回原因，给车公司的说明" />
          <div className="mt-3 flex flex-wrap gap-2">
            <Button disabled={!canRequestCarrierApproval || changeRequestMutation.isPending} onClick={submitModify}>
              <FilePenLine size={16} />
              申请修改
            </Button>
            <Button variant="secondary" disabled={!canRequestCarrierApproval || changeRequestMutation.isPending} onClick={() => submitCancel(false)}>
              <Undo2 size={16} />
              申请撤销
            </Button>
            <Button variant="secondary" className="text-red-600" disabled={!canRequestCarrierApproval || changeRequestMutation.isPending} onClick={() => submitCancel(true)}>
              强制取消申请
            </Button>
          </div>
          <div className="mt-3 rounded-md bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-500">
            订单还在大厅且未接单时可以直接撤回；已接单后，修改或撤销会提交给车公司确认；已完成收款的订单不再允许变更或撤销。
          </div>
          {selectedRequests.length ? (
            <div className="mt-3 overflow-hidden rounded-lg border border-border">
              <table className="data-table min-w-[720px]">
                <thead><tr><th>类型</th><th>状态</th><th>费用</th><th>说明</th><th>时间</th></tr></thead>
                <tbody>
                  {selectedRequests.map((item) => (
                    <tr key={item.id}>
                      <td>{item.request_type === "cancel" ? "撤销" : "修改"}</td>
                      <td><StatusBadge status={item.status} /></td>
                      <td>{item.fee_percent || 0}% / {item.fee_amount_jpy || 0} JPY</td>
                      <td>{item.policy_message || item.reason || "-"}</td>
                      <td>{item.created_at || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function AgencySettlementPanel({ rows, message, uploadPaymentReceiptMutation }: { rows: Order[]; message: string; uploadPaymentReceiptMutation: UploadReceiptMutation }) {
  const settlementRows = sortAgencyHallOrders(rows).filter((order) =>
    ["payment_requested", "receipt_uploaded", "paid", "settled"].includes(order.settlement_status || order.agency_settlement_status || ""),
  );
  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-50 px-3 py-2">
        <div>
          <div className="text-sm font-bold text-slate-950">费用结算</div>
          <div className="mt-1 text-xs font-semibold text-slate-500">车公司发起付款请求，旅行社付款后上传回执，车公司确认收款后订单完成。</div>
        </div>
        {message ? <div className="rounded-md bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-700">{message}</div> : null}
      </div>
      {uploadPaymentReceiptMutation.error instanceof Error ? <div className="mx-3 my-2 text-sm font-semibold text-red-600">{uploadPaymentReceiptMutation.error.message}</div> : null}
      <div className="overflow-x-auto">
      <table className="data-table min-w-[1320px]">
        <thead>
          <tr>
            <th className="min-w-[220px] whitespace-nowrap">订单</th>
            <th className="min-w-[420px] whitespace-nowrap">行程</th>
            <th className="min-w-[120px] whitespace-nowrap">请求金额</th>
            <th className="min-w-[120px] whitespace-nowrap">结算状态</th>
            <th className="min-w-[180px] whitespace-nowrap">付款请求</th>
            <th className="min-w-[160px] whitespace-nowrap">回执</th>
            <th className="min-w-[120px] whitespace-nowrap">操作</th>
          </tr>
        </thead>
        <tbody>
          {settlementRows.length ? settlementRows.map((order) => (
            <tr key={order.id}>
              <td className="whitespace-nowrap font-bold text-slate-950">{order.oid || order.id}</td>
              <td className="whitespace-nowrap">{order.order_date} {order.start_time || ""} / {order.pickup_location || "-"} {"->"} {order.dropoff_location || "-"}</td>
              <td className="whitespace-nowrap">{order.payment_amount_jpy || order.price_jpy || order.price || "-"}</td>
              <td className="whitespace-nowrap"><StatusBadge status={order.settlement_status || order.agency_settlement_status} /></td>
              <td>{order.carrier_payment_requested_at || "-"}<br /><span className="text-xs text-slate-500">{order.carrier_payment_request_note || ""}</span></td>
              <td className="whitespace-nowrap">
                {order.agency_payment_receipt_name || "-"}
                {order.agency_payment_receipt_url ? (
                  <a className="ml-2 text-blue-700 hover:underline" href={apiAssetUrl(order.agency_payment_receipt_url)} target="_blank" rel="noreferrer">查看</a>
                ) : null}
              </td>
              <td className="whitespace-nowrap">
                <label className={`inline-flex h-8 items-center gap-1 rounded-md border px-2 text-xs font-bold ${order.settlement_status === "paid" ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400" : "cursor-pointer border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100"}`}>
                  <Upload size={14} />
                  上传回执
                  <input
                    className="sr-only"
                    type="file"
                    accept="image/*,application/pdf,.pdf"
                    disabled={order.settlement_status === "paid" || uploadPaymentReceiptMutation.isPending}
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) uploadPaymentReceiptMutation.mutate({ orderId: order.id, file });
                      event.currentTarget.value = "";
                    }}
                  />
                </label>
              </td>
            </tr>
          )) : <tr><td colSpan={7} className="py-8 text-center text-sm text-slate-500">暂无待结算订单</td></tr>}
        </tbody>
      </table>
      </div>
    </div>
  );
}

function sortAgencyHallOrders(rows: Order[]) {
  const rank = (order: Order) => {
    const settlement = order.settlement_status || order.agency_settlement_status || "";
    const status = order.auction_status || order.dispatch_status || "";
    if (["payment_requested", "receipt_uploaded"].includes(settlement)) return 0;
    if (["listed", "bidding", "auction_listed"].includes(status)) return 1;
    if (["claimed", "auction_claimed", "assigned"].includes(status)) return 2;
    if (["unassigned"].includes(status)) return 3;
    if (["expired", "auction_expired"].includes(status)) return 4;
    if (["cancelled", "auction_cancelled"].includes(status)) return 5;
    if (["paid", "settled"].includes(settlement) || order.execution_status === "completed") return 6;
    return 7;
  };
  return [...rows].sort((a, b) => {
    const diff = rank(a) - rank(b);
    if (diff) return diff;
    return `${a.order_date || ""} ${a.start_time || ""}`.localeCompare(`${b.order_date || ""} ${b.start_time || ""}`);
  });
}

function filterAgencyHallOrders(rows: Order[], filter: string) {
  if (filter === "all") return rows;
  return rows.filter((order) => {
    const status = order.auction_status || order.dispatch_status || "";
    const settlement = order.settlement_status || order.agency_settlement_status || "";
    if (filter === "ongoing") return !["expired", "auction_expired", "cancelled", "auction_cancelled"].includes(status) && !["paid", "settled"].includes(settlement);
    if (filter === "publishing") return ["listed", "bidding"].includes(order.auction_status || "") || order.dispatch_status === "auction_listed";
    if (filter === "claimed") return ["claimed", "auction_claimed", "assigned"].includes(status);
    if (filter === "expired") return ["expired", "auction_expired"].includes(status);
    if (filter === "withdrawn") return ["cancelled", "auction_cancelled"].includes(status);
    if (filter === "pending_payment") return ["payment_requested", "receipt_uploaded"].includes(settlement);
    if (filter === "completed") return ["paid", "settled"].includes(settlement) || order.execution_status === "completed";
    return true;
  });
}

function isRepublishableOrder(order: Order) {
  const status = order.auction_status || order.dispatch_status || "";
  return ["expired", "auction_expired", "cancelled", "auction_cancelled"].includes(status);
}

function canPublishToHall(order: Order) {
  const status = order.auction_status || order.dispatch_status || "unassigned";
  return ["unassigned", "expired", "auction_expired", "cancelled", "auction_cancelled"].includes(status);
}

function canDirectEditAgencyOrder(order: Order) {
  return canPublishToHall(order) && !isClosedForAgencyAction(order);
}

function isClosedForAgencyAction(order: Order) {
  return ["paid", "settled"].includes(order.settlement_status || order.agency_settlement_status || "") || ["completed", "cancelled"].includes(order.execution_status || "");
}

function agencyAuctionStatusLabel(order: Order) {
  const status = order.auction_status || order.dispatch_status || "";
  if (["expired", "auction_expired"].includes(status)) return "超时撤回";
  if (["cancelled", "auction_cancelled"].includes(status)) return "已撤回";
  if (["listed", "bidding", "auction_listed"].includes(status)) return "发布中";
  if (["claimed", "auction_claimed", "assigned"].includes(status)) return "已接单";
  if (!status || status === "unassigned") return "未发布";
  return status;
}

function AgencyAuctionStatusBadge({ order }: { order: Order }) {
  if (isRepublishableOrder(order)) {
    const expired = ["expired", "auction_expired"].includes(order.auction_status || order.dispatch_status || "");
    return (
      <span className={`inline-flex h-6 items-center rounded-full px-2 text-xs font-semibold ring-1 ${expired ? "bg-amber-50 text-amber-700 ring-amber-200" : "bg-slate-100 text-slate-700 ring-slate-300"}`}>
        {agencyAuctionStatusLabel(order)}
      </span>
    );
  }
  return <StatusBadge status={order.auction_status || order.dispatch_status} />;
}

function HallViewButton({ active, label, count, onClick }: { active: boolean; label: string; count: number; onClick: () => void }) {
  return (
    <button
      className={`inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-bold ${active ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}
      onClick={onClick}
    >
      <span>{label}</span>
      <span className={`rounded-full px-2 py-0.5 text-xs ${active ? "bg-white/20 text-white" : "bg-white text-slate-500"}`}>{count}</span>
    </button>
  );
}

function HallListingTable({ title, rows }: { title: string; rows: AuctionListing[] }) {
  const [filters, setFilters] = useState({ date: "", time: "", keyword: "" });
  const filteredRows = rows.filter((item) => {
    const dateOk = !filters.date || String(item.order_date || "").slice(0, 10) === filters.date;
    const timeOk = !filters.time || String(item.start_time || "").startsWith(filters.time);
    const keyword = filters.keyword.trim().toLowerCase();
    const keywordOk = !keyword || [item.pickup_location, item.dropoff_location, item.vehicle_type, item.order_type].filter(Boolean).join(" ").toLowerCase().includes(keyword);
    return dateOk && timeOk && keywordOk;
  });
  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-50 px-3 py-2">
        <div className="text-sm font-bold text-slate-950">{title}</div>
        <div className="flex flex-wrap gap-2">
          <input className="h-8 rounded-md border border-border px-2 text-xs" type="date" value={filters.date} onChange={(event) => setFilters({ ...filters, date: event.target.value })} />
          <input className="h-8 rounded-md border border-border px-2 text-xs" type="time" value={filters.time} onChange={(event) => setFilters({ ...filters, time: event.target.value })} />
          <input className="h-8 w-52 rounded-md border border-border px-2 text-xs" placeholder="筛选接机/送机/地点/车型" value={filters.keyword} onChange={(event) => setFilters({ ...filters, keyword: event.target.value })} />
        </div>
      </div>
      <div className="overflow-x-auto">
      <table className="data-table min-w-[1360px]">
        <thead>
          <tr>
            <th className="min-w-[160px] whitespace-nowrap">类型</th>
            <th className="min-w-[170px] whitespace-nowrap">日期时间</th>
            <th className="min-w-[430px] whitespace-nowrap">主要行程</th>
            <th className="min-w-[130px] whitespace-nowrap">车型</th>
            <th className="min-w-[100px] whitespace-nowrap">行程PDF</th>
            <th className="min-w-[150px] whitespace-nowrap">起拍/一口价</th>
            <th className="min-w-[170px] whitespace-nowrap">拍卖截止</th>
            <th className="min-w-[110px] whitespace-nowrap">状态</th>
          </tr>
        </thead>
        <tbody>
          {filteredRows.length ? filteredRows.map((item, index) => (
            <tr key={item.id}>
              <td className="whitespace-nowrap font-bold text-slate-950">
                {isAirportTransfer(item) ? "机场接送" : "包车"}
                <div className="mt-1 text-xs font-semibold text-slate-500">公开单 {index + 1}</div>
              </td>
              <td className="whitespace-nowrap">{item.order_date} {item.start_time}-{item.end_time}</td>
              <td className="whitespace-nowrap">{item.pickup_location || "-"} {"->"} {item.dropoff_location || "-"}</td>
              <td className="whitespace-nowrap">{item.vehicle_type || "-"}</td>
              <td className="whitespace-nowrap">{item.has_itinerary_pdf ? "有 PDF" : "-"}</td>
              <td className="whitespace-nowrap">{item.start_price_jpy || 0} / {item.buyout_price_jpy || 0}</td>
              <td className="whitespace-nowrap">{item.expires_at || "-"}</td>
              <td className="whitespace-nowrap"><StatusBadge status={item.status} /></td>
            </tr>
          )) : <tr><td colSpan={8} className="py-8 text-center text-sm text-slate-500">暂无符合筛选的公开订单</td></tr>}
        </tbody>
      </table>
      </div>
    </div>
  );
}

function MapTrackingPanel({ rows, selectedId, setSelectedId }: { rows: Order[]; selectedId: number | null; setSelectedId: (value: number) => void }) {
  const selected = useMemo(() => {
    if (!rows.length) return null;
    return rows.find((order) => order.id === selectedId) || rows[0];
  }, [rows, selectedId]);
  const hasDriverMap = Boolean(selected?.driver_latitude && selected?.driver_longitude);
  return (
    <section className="grid gap-6 xl:grid-cols-[420px_minmax(0,1fr)] 2xl:grid-cols-[460px_minmax(0,1fr)]">
      <Card>
        <CardHeader>
          <h2 className="text-base font-bold text-slate-950">地图追踪</h2>
          <p className="mt-1 text-sm text-slate-500">查看订单路线、司机最新位置、司机和车辆信息。</p>
        </CardHeader>
        <CardContent className="max-h-[660px] space-y-3 overflow-y-auto">
          {rows.length ? rows.map((order) => (
            <button
              key={order.id}
              className={`w-full rounded-lg border p-3 text-left ${selected?.id === order.id ? "border-blue-500 bg-blue-50" : "border-border bg-white hover:bg-slate-50"}`}
              onClick={() => setSelectedId(order.id)}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-bold text-slate-950">{order.oid || order.id}</div>
                  <div className="mt-1 text-xs font-semibold text-slate-500">{order.order_date} {order.start_time || ""}</div>
                </div>
                <StatusBadge status={order.dispatch_status} />
              </div>
              <div className="mt-2 text-sm text-slate-600">{order.pickup_location || "-"} {"->"} {order.dropoff_location || "-"}</div>
              <DriverVehicleSummary order={order} />
            </button>
          )) : <div className="py-10 text-center text-sm text-slate-500">暂无可追踪订单</div>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-base font-bold text-slate-950">{selected?.oid || selected?.id || "未选择订单"}</h2>
              <p className="mt-1 text-sm text-slate-500">{selected ? `${selected.pickup_location || "-"} -> ${selected.dropoff_location || "-"}` : "请选择左侧订单"}</p>
            </div>
            {selected ? <StatusBadge status={selected.execution_status || selected.dispatch_status} /> : null}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {selected ? (
            <>
              <div className="grid gap-3 md:grid-cols-2">
                <InfoBlock icon={<UserRound size={18} />} title="司机信息" lines={[
                  selected.driver_name || "等待车公司派司机",
                  selected.driver_phone ? `电话：${selected.driver_phone}` : "",
                  selected.assigned_driver_code ? `司机编号：${selected.assigned_driver_code}` : "",
                  selected.assigned_driver_language ? `语言：${selected.assigned_driver_language}` : "",
                ]} />
                <InfoBlock icon={<CarFront size={18} />} title="车辆信息" lines={[
                  selected.plate_number || selected.plate_no || "等待车公司派车辆",
                  selected.assigned_vehicle_type || selected.vehicle_type ? `车型：${selected.assigned_vehicle_type || selected.vehicle_type}` : "",
                  selected.seat_count ? `座位：${selected.seat_count}` : "",
                  selected.assigned_vehicle_color ? `颜色：${selected.assigned_vehicle_color}` : "",
                ]} />
              </div>
              <div className="rounded-lg border border-border bg-slate-50 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-sm font-bold text-slate-950">司机最新位置</div>
                  <div className="text-xs font-semibold text-slate-500">{selected.driver_location_reported_at || "未上报"}</div>
                </div>
                <div className="mt-2 text-sm text-slate-600">
                  {selected.driver_location_text || "等待司机端上报位置"}
                  {selected.driver_latitude && selected.driver_longitude ? ` (${selected.driver_latitude}, ${selected.driver_longitude})` : ""}
                </div>
              </div>
              {hasDriverMap ? (
                <div className="overflow-hidden rounded-lg border border-border bg-white">
                  <iframe title="订单地图追踪" className="h-[520px] w-full" src={driverMapUrl(selected)} />
                </div>
              ) : (
                <MapStatusPlaceholder order={selected} />
              )}
            </>
          ) : (
            <div className="py-20 text-center text-sm text-slate-500">暂无订单数据</div>
          )}
        </CardContent>
      </Card>
    </section>
  );
}

function MapStatusPlaceholder({ order }: { order: Order }) {
  const label = agencyAuctionStatusLabel(order);
  return (
    <div className="flex min-h-[520px] items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center">
      <div>
        <div className="mx-auto inline-flex rounded-full bg-amber-50 px-4 py-2 text-sm font-black text-amber-700 ring-1 ring-amber-200">
          {label}
        </div>
        <div className="mt-5 text-lg font-black text-slate-950">{order.oid || order.id}</div>
        <div className="mt-2 text-sm font-semibold text-slate-500">
          {order.pickup_location || "-"} {"->"} {order.dropoff_location || "-"}
        </div>
        <div className="mt-4 text-sm text-slate-500">
          车公司接单并分配司机、司机端上报位置后，这里再显示地图追踪。
        </div>
      </div>
    </div>
  );
}

function OrderRequestPanel({
  rows,
  requests,
  selectedId,
  setSelectedId,
  message,
  withdrawMutation,
  changeRequestMutation,
}: {
  rows: Order[];
  requests: AgencyOrderChangeRequest[];
  selectedId: number | null;
  setSelectedId: (value: number) => void;
  message: string;
  withdrawMutation: ReturnType<typeof useMutation<{ result: { success: boolean; mode: string; order_id: number; listing_id?: number } }, Error, number>>;
  changeRequestMutation: ReturnType<typeof useMutation<{ request: AgencyOrderChangeRequest }, Error, { orderId: number; payload: { request_type: "modify" | "cancel"; reason?: string; force?: boolean; changes?: Partial<Order> } }>>;
}) {
  const selected = rows.find((order) => order.id === selectedId) || rows[0];
  const [reason, setReason] = useState("");
  const [force, setForce] = useState(false);
  const [changes, setChanges] = useState<Partial<Order>>({});
  const accepted = selected ? ["auction_claimed", "claimed", "assigned"].includes(selected.dispatch_status || "") || Boolean(selected.assignment_id) : false;
  const canDirectWithdraw = selected ? ["auction_listed", "bidding"].includes(selected.dispatch_status || "") && !accepted : false;
  const selectedRequests = selected ? requests.filter((item) => item.order_id === selected.id) : [];

  function submitModify() {
    if (!selected) return;
    changeRequestMutation.mutate({ orderId: selected.id, payload: { request_type: "modify", reason, changes } });
  }

  function submitCancel() {
    if (!selected) return;
    changeRequestMutation.mutate({ orderId: selected.id, payload: { request_type: "cancel", reason, force } });
  }

  return (
    <section className="grid gap-6 xl:grid-cols-[360px_1fr]">
      <Card>
        <CardHeader>
          <h2 className="text-base font-bold text-slate-950">变更/撤回</h2>
          <p className="mt-1 text-sm text-slate-500">未接单可撤回大厅；已接单需车公司确认。</p>
        </CardHeader>
        <CardContent className="space-y-3">
          <select className="h-10 w-full rounded-md border border-border px-3 text-sm" value={selected?.id || ""} onChange={(event) => setSelectedId(Number(event.target.value))}>
            {rows.map((order) => (
              <option key={order.id} value={order.id}>{order.oid || order.id} / {order.order_date} {order.start_time || ""}</option>
            ))}
          </select>
          <div className="rounded-lg border border-border bg-slate-50 p-3 text-sm text-slate-600">
            <div className="font-bold text-slate-950">{selected?.pickup_location || "-"} {"->"} {selected?.dropoff_location || "-"}</div>
            <div className="mt-2">状态：{selected?.dispatch_status || "-"}</div>
            <div className="mt-1">最近申请：{selected?.latest_change_request_status || "无"}</div>
          </div>
          <div className="rounded-lg border border-amber-100 bg-amber-50 p-3 text-xs leading-5 text-amber-800">
            超过24小时且本月免费额度未满10单，车公司确认后免费撤销；不满足免费条件或强制取消按规则产生费用，6小时内强制取消按全额费用处理。
          </div>
          {message ? <div className="rounded-md bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700">{message}</div> : null}
          {withdrawMutation.error instanceof Error ? <div className="text-sm font-semibold text-red-600">{withdrawMutation.error.message}</div> : null}
          {changeRequestMutation.error instanceof Error ? <div className="text-sm font-semibold text-red-600">{changeRequestMutation.error.message}</div> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="text-base font-bold text-slate-950">操作</h2>
          <p className="mt-1 text-sm text-slate-500">关键字段修改不会直接生效，车公司同意后才写入订单。</p>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" disabled={!selected || !canDirectWithdraw || withdrawMutation.isPending} onClick={() => selected && withdrawMutation.mutate(selected.id)}>
              <Undo2 size={16} />
              未接单撤回大厅
            </Button>
            <Button variant="secondary" disabled={!selected || !accepted || changeRequestMutation.isPending} onClick={submitCancel}>
              <Undo2 size={16} />
              申请撤销订单
            </Button>
          </div>
          <label className="flex items-center gap-2 text-sm font-semibold text-slate-700">
            <input type="checkbox" checked={force} onChange={(event) => setForce(event.target.checked)} />
            标记为强制取消申请
          </label>
          <textarea className="min-h-20 w-full rounded-md border border-border px-3 py-2 text-sm" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="原因 / 给车公司的说明" />

          <div className="rounded-lg border border-border p-3">
            <div className="mb-3 flex items-center gap-2 text-sm font-bold text-slate-950">
              <FilePenLine size={16} />
              关键字段修改申请
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <Field label="开始日期" type="date" value={changes.order_date ?? selected?.order_date ?? ""} onChange={(value) => setChanges({ ...changes, order_date: value })} />
              <Field label="开始时间" type="time" value={changes.start_time ?? selected?.start_time ?? ""} onChange={(value) => setChanges({ ...changes, start_time: value })} />
              <Field label="起点" value={changes.pickup_location ?? selected?.pickup_location ?? ""} onChange={(value) => setChanges({ ...changes, pickup_location: value })} />
              <Field label="终点" value={changes.dropoff_location ?? selected?.dropoff_location ?? ""} onChange={(value) => setChanges({ ...changes, dropoff_location: value })} />
              <Field label="车型" value={changes.vehicle_type ?? selected?.vehicle_type ?? ""} onChange={(value) => setChanges({ ...changes, vehicle_type: value })} />
              <Field label="报价 JPY" type="number" value={changes.price ?? selected?.price ?? ""} onChange={(value) => setChanges({ ...changes, price: value ? Number(value) : undefined, price_jpy: value ? Number(value) : undefined })} />
            </div>
            <Button className="mt-3" disabled={!selected || changeRequestMutation.isPending} onClick={submitModify}>
              <FilePenLine size={16} />
              提交修改申请
            </Button>
          </div>

          <div className="overflow-hidden rounded-lg border border-border">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="bg-slate-50 text-xs font-bold text-slate-500">
                <tr><th className="px-3 py-2">类型</th><th className="px-3 py-2">状态</th><th className="px-3 py-2">费用</th><th className="px-3 py-2">说明</th><th className="px-3 py-2">时间</th></tr>
              </thead>
              <tbody>
                {selectedRequests.length ? selectedRequests.map((item) => (
                  <tr key={item.id} className="border-t border-border">
                    <td className="px-3 py-2">{item.request_type === "cancel" ? "撤销" : "修改"}</td>
                    <td className="px-3 py-2"><StatusBadge status={item.status} /></td>
                    <td className="px-3 py-2">{item.fee_percent || 0}% / {item.fee_amount_jpy || 0} JPY</td>
                    <td className="px-3 py-2">{item.policy_message || item.reason || "-"}</td>
                    <td className="px-3 py-2">{item.created_at || "-"}</td>
                  </tr>
                )) : <tr><td className="px-3 py-8 text-center text-slate-500" colSpan={5}>暂无申请记录</td></tr>}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </section>
  );
}

const agencyCalendarRanges = [1, 7, 15] as const;
type AgencyCalendarRange = (typeof agencyCalendarRanges)[number];
type AgencyCalendarStatus = "unpublished" | "published" | "claimed" | "progress" | "completed" | "expired" | "cancelled";

const agencyCalendarLabelColumn = "minmax(180px, 240px)";

function CalendarPanel({ date, setDate, rows, allRows, publishMutation }: { date: string; setDate: (value: string) => void; rows: Order[]; allRows: Order[]; publishMutation: PublishAuctionMutation }) {
  const queryClient = useQueryClient();
  const [rangeDays, setRangeDays] = useState<AgencyCalendarRange>(7);
  const [calendarDraft, setCalendarDraft] = useState<{ mode: "create" | "edit"; order?: Order; form: Partial<Order> } | null>(null);
  const dateOptions = Array.from(new Set(allRows.map((order) => (order.order_date || "").slice(0, 10)).filter(Boolean))).sort();
  const selectedDateKey = resolveCalendarDate(date, dateOptions);
  const rangeStart = parseDateKey(selectedDateKey);
  const rangeDates = buildDateRange(rangeStart, rangeDays);
  const rangeEndKey = formatDateKey(rangeDates[rangeDates.length - 1] || rangeStart);
  const visibleRows = allRows
    .filter((order) => orderOverlapsRange(order, selectedDateKey, rangeEndKey))
    .sort((a, b) => `${orderStartKey(a)} ${a.start_time || ""}`.localeCompare(`${orderStartKey(b)} ${b.start_time || ""}`));
  const charterRows = visibleRows.filter((order) => isCharterOrder(order));
  const statusCounts = visibleRows.reduce(
    (acc, order) => {
      acc[agencyCalendarStatusProfile(order).key] += 1;
      return acc;
    },
    { unpublished: 0, published: 0, claimed: 0, progress: 0, completed: 0, expired: 0, cancelled: 0 } satisfies Record<AgencyCalendarStatus, number>,
  );

  function shiftRange(delta: number) {
    setDate(formatDateKey(addDays(rangeStart, delta * rangeDays)));
  }

  const saveCalendarDraftMutation = useMutation({
    mutationFn: async ({ publish = false }: { publish?: boolean } = {}) => {
      if (!calendarDraft) throw new Error("no_calendar_draft");
      let result: { order: Order };
      if (calendarDraft.mode === "edit" && calendarDraft.order?.id) {
        result = await api.updateAgencyPortalOrder(calendarDraft.order.id, calendarDraft.form);
      } else {
        result = await api.createAgencyPortalOrder(calendarDraft.form);
      }
      if (publish && result.order?.id) {
        const price = Number(result.order.price_jpy || result.order.price || calendarDraft.form.price_jpy || calendarDraft.form.price || 0);
        await api.publishAgencyPortalOrderToAuction(result.order.id, {
          start_price_jpy: price,
          buyout_price_jpy: price,
          auction_duration_hours: 2,
          note: "从日历保存后发布",
        });
      }
      return result;
    },
    onSuccess: async () => {
      setCalendarDraft(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["agency-portal-orders"] }),
        queryClient.invalidateQueries({ queryKey: ["agency-portal-auction-listings"] }),
      ]);
    },
  });

  function openCalendarCreate(value: string) {
    const [day, time] = value.split(" ");
    const startTime = time || "09:00";
    setCalendarDraft({
      mode: "create",
      form: {
        ...emptyOrder,
        order_date: day,
        end_date: day,
        start_time: startTime,
        end_time: addHours(startTime, 10),
        order_type: "包车",
      },
    });
  }

  function openCalendarEdit(order: Order) {
    if (!agencyCalendarCanEdit(order)) {
      window.alert(`该订单已进入发布/承接流程，不能直接修改。\n请到“我的订单”提交变更申请：${order.oid || order.id}`);
      return;
    }
    setCalendarDraft({ mode: "edit", order, form: { ...order } });
  }

  return (
    <section>
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-bold text-slate-950">订单日历条</h2>
              <p className="mt-1 text-sm text-slate-500">一屏显示 24h / 7d / 15d；悬浮查看详情，双击未发布订单修改，双击空白处新建。</p>
            </div>
            <div className="min-w-[240px]">
              <div className="mb-1 text-xs font-bold text-slate-600">起始日期</div>
              <div className="flex items-center gap-2">
                <Button variant="secondary" className="h-10 w-10 shrink-0 px-0" aria-label="上一段" onClick={() => shiftRange(-1)}>
                  <ChevronLeft size={16} />
                </Button>
                <input
                  className="h-10 w-[150px] rounded-md border border-border px-3 text-sm font-semibold text-slate-700"
                  type="date"
                  value={selectedDateKey}
                  onChange={(event) => setDate(event.target.value)}
                />
                <Button variant="secondary" className="h-10 w-10 shrink-0 px-0" aria-label="下一段" onClick={() => shiftRange(1)}>
                  <ChevronRight size={16} />
                </Button>
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-2">
              {agencyCalendarRanges.map((item) => (
                <button
                  key={item}
                  className={`h-9 rounded-md px-3 text-xs font-black ${rangeDays === item ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}
                  onClick={() => setRangeDays(item)}
                >
                  {calendarRangeLabel(item)}
                </button>
              ))}
            </div>
            <div className="text-sm font-bold text-slate-500">
              {selectedDateKey} 至 {rangeEndKey} · {visibleRows.length} 单
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-6">
            <CalendarMetric label="未发布" value={statusCounts.unpublished} tone="slate" />
            <CalendarMetric label="已发布" value={statusCounts.published} tone="amber" />
            <CalendarMetric label="已接单" value={statusCounts.claimed} tone="blue" />
            <CalendarMetric label="进行中" value={statusCounts.progress} tone="violet" />
            <CalendarMetric label="已完成" value={statusCounts.completed} tone="green" />
            <CalendarMetric label="包车" value={charterRows.length} tone="teal" />
          </div>

          <div className="flex flex-wrap gap-3 text-xs font-bold text-slate-500">
            <CalendarLegend color="bg-slate-400" label="未发布" />
            <CalendarLegend color="bg-amber-500" label="已发布/竞拍中" />
            <CalendarLegend color="bg-blue-500" label="已接单/已派车" />
            <CalendarLegend color="bg-violet-500" label="进行中" />
            <CalendarLegend color="bg-emerald-500" label="已完成" />
            <CalendarLegend color="bg-zinc-500" label="流拍" />
            <CalendarLegend color="bg-red-500" label="已取消" />
          </div>

          {rangeDays === 1 ? (
            <AgencyDailyTimeline rows={visibleRows} selectedDateKey={selectedDateKey} onCreate={openCalendarCreate} onEdit={openCalendarEdit} />
          ) : (
            <div className="overflow-hidden rounded-lg border border-border bg-white">
              <div>
                <div
                  className="sticky top-0 z-20 grid border-b border-border bg-slate-50"
                  style={{ gridTemplateColumns: `${agencyCalendarLabelColumn} repeat(${rangeDates.length}, minmax(0, 1fr))` }}
                >
                  <div className="sticky left-0 z-30 border-r border-border bg-slate-50 px-4 py-3 text-sm font-black text-slate-700">订单编号</div>
                  {rangeDates.map((day) => {
                    const key = formatDateKey(day);
                    const keyOrderCount = allRows.filter((order) => orderTouchesDate(order, key)).length;
                    return (
                    <button
                      key={key}
                      className={`border-r border-border px-2 py-3 text-left ${key === selectedDateKey ? "bg-blue-50" : "bg-slate-50 hover:bg-white"}`}
                      onClick={() => setDate(key)}
                      onDoubleClick={() => openCalendarCreate(key)}
                    >
                        <div className={`text-xs font-black ${key === selectedDateKey ? "text-blue-700" : "text-slate-700"}`}>{key.slice(5)}</div>
                        <div className="mt-1 flex items-center justify-between gap-2 text-[11px] font-bold text-slate-400">
                          <span>{weekdayLabel(day)}</span>
                          {keyOrderCount ? <span className="rounded-full bg-slate-900 px-1.5 py-0.5 text-white">{keyOrderCount}</span> : null}
                        </div>
                      </button>
                    );
                  })}
                </div>

                {visibleRows.length ? visibleRows.map((order, index) => (
                  <AgencyCalendarStripRow
                    key={order.id || `${order.order_date}-${index}`}
                    order={order}
                    rangeStart={rangeStart}
                    rangeDates={rangeDates}
                    selectedDateKey={selectedDateKey}
                    onSelectDate={setDate}
                    onCreate={openCalendarCreate}
                    onEdit={openCalendarEdit}
                  />
                )) : (
                  <div className="py-12 text-center text-sm font-semibold text-slate-500">当前时间窗口暂无订单</div>
                )}
              </div>
            </div>
          )}

          <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-3 py-2 text-xs font-semibold leading-5 text-slate-500">
            日历条的左右边界表示订单开始和结束；颜色表示订单状态。只有大厅竞拍截止时间会额外显示“截止”标记。
          </div>
        </CardContent>
      </Card>
      {calendarDraft ? (
        <CalendarDraftDialog
          draft={calendarDraft}
          setDraft={setCalendarDraft}
          isSaving={saveCalendarDraftMutation.isPending}
          error={saveCalendarDraftMutation.error}
          onSave={(publish) => saveCalendarDraftMutation.mutate({ publish })}
          canPublish={Boolean(calendarDraft.form.price_jpy || calendarDraft.form.price)}
          isPublishing={publishMutation.isPending}
        />
      ) : null}
    </section>
  );
}

function calendarRangeLabel(value: AgencyCalendarRange) {
  if (value === 1) return "24h";
  return `${value}d`;
}

function AgencyDailyTimeline({
  rows,
  selectedDateKey,
  onCreate,
  onEdit,
}: {
  rows: Order[];
  selectedDateKey: string;
  onCreate: (value: string) => void;
  onEdit: (order: Order) => void;
}) {
  const charterRows = rows.filter(isCharterOrder);
  const otherRows = rows.filter((order) => !isCharterOrder(order));
  const groups = [
    { key: "charter", label: "包车订单", rows: charterRows },
    { key: "other", label: "接送机/其他", rows: otherRows },
  ].filter((group) => group.rows.length);

  return (
    <div className="overflow-visible rounded-lg border border-border bg-white">
      <div>
        <div
          className="sticky top-0 z-20 grid border-b border-border bg-slate-50"
          style={{ gridTemplateColumns: `${agencyCalendarLabelColumn} repeat(24, minmax(0, 1fr))` }}
        >
          <div className="sticky left-0 z-30 border-r border-border bg-slate-50 px-4 py-3 text-sm font-black text-slate-700">{selectedDateKey}</div>
          {Array.from({ length: 24 }, (_, hour) => (
            <button
              key={hour}
              className="border-r border-border px-1 py-3 text-left text-[11px] font-black text-slate-600 hover:bg-white"
              onDoubleClick={() => onCreate(`${selectedDateKey} ${String(hour).padStart(2, "0")}:00`)}
            >
              {String(hour).padStart(2, "0")}:00
            </button>
          ))}
        </div>
        {groups.length ? groups.map((group) => (
          <AgencyDailyTimelineRow key={group.key} label={group.label} rows={group.rows} selectedDateKey={selectedDateKey} onCreate={onCreate} onEdit={onEdit} />
        )) : (
          <div className="py-12 text-center text-sm font-semibold text-slate-500">当前 24h 窗口暂无订单</div>
        )}
      </div>
    </div>
  );
}

function AgencyDailyTimelineRow({
  label,
  rows,
  selectedDateKey,
  onCreate,
  onEdit,
}: {
  label: string;
  rows: Order[];
  selectedDateKey: string;
  onCreate: (value: string) => void;
  onEdit: (order: Order) => void;
}) {
  const rowHeight = 104;
  return (
    <div
      className="relative grid border-b border-border last:border-b-0"
      style={{ gridTemplateColumns: `${agencyCalendarLabelColumn} minmax(0, 1fr)`, minHeight: rowHeight }}
    >
      <div className="sticky left-0 z-10 border-r border-border bg-white px-4 py-3">
        <div className="text-sm font-black text-slate-950">{label}</div>
        <div className="mt-1 text-xs font-semibold text-slate-500">{rows.length} 单，同一天内按时间段排在一行</div>
      </div>
      <div className="relative bg-white" onDoubleClick={() => onCreate(selectedDateKey)}>
        {Array.from({ length: 24 }, (_, hour) => (
          <div key={hour} className="absolute bottom-0 top-0 border-r border-slate-100" style={{ left: `${(hour / 24) * 100}%`, width: `${100 / 24}%` }} />
        ))}
        {rows.map((order, index) => {
          const profile = agencyCalendarStatusProfile(order);
          const start = timeToMinutes(order.start_time) ?? 0;
          const effectiveEnd = effectiveOrderEndTime(order);
          const end = timeToMinutes(effectiveEnd) ?? defaultEndMinutes(order);
          const safeEnd = end > start ? end : defaultEndMinutes(order);
          const left = `${(Math.max(0, Math.min(start, 24 * 60 - 15)) / (24 * 60)) * 100}%`;
          const width = `${Math.max(3.5, ((safeEnd - start) / (24 * 60)) * 100)}%`;
          return (
            <div
              key={order.id || `${order.start_time}-${index}`}
              className={`group absolute top-5 rounded-md border px-2 py-2 text-xs font-bold shadow-sm ${profile.barClass}`}
              style={{ left, width, minHeight: 54 }}
              title={`${agencyCalendarOrderCode(order)}\n${order.start_time || "--:--"}-${effectiveEnd}\n${order.pickup_location || "-"} -> ${order.dropoff_location || "-"}`}
              onDoubleClick={(event) => {
                event.stopPropagation();
                onEdit(order);
              }}
            >
              <div className="truncate">{order.start_time || "--:--"}-{effectiveEnd} {order.vehicle_type || ""}</div>
              <div className="mt-1 truncate opacity-80">{order.pickup_location || "-"} {"->"} {order.dropoff_location || "-"}</div>
              <CalendarOrderTooltip order={order} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AgencyCalendarStripRow({
  order,
  rangeStart,
  rangeDates,
  selectedDateKey,
  onSelectDate,
  onCreate,
  onEdit,
}: {
  order: Order;
  rangeStart: Date;
  rangeDates: Date[];
  selectedDateKey: string;
  onSelectDate: (date: string) => void;
  onCreate: (value: string) => void;
  onEdit: (order: Order) => void;
}) {
  const profile = agencyCalendarStatusProfile(order);
  const placement = calendarBarPlacement(order, rangeStart, rangeDates.length);
  const markers = calendarKeyMarkers(order, rangeStart, rangeDates.length);
  const route = `${order.pickup_location || "-"} -> ${order.dropoff_location || "-"}`;
  const rowHeight = 86;
  return (
    <div
      className="relative grid border-b border-border last:border-b-0"
      style={{ gridTemplateColumns: `${agencyCalendarLabelColumn} repeat(${rangeDates.length}, minmax(0, 1fr))`, minHeight: rowHeight }}
    >
      <div className="sticky left-0 z-10 border-r border-border bg-white px-4 py-3">
        <div className="flex items-center gap-2">
          <span className={`rounded-full px-2 py-1 text-[11px] font-black ${profile.badgeClass}`}>{profile.label}</span>
          <span className={`rounded-full px-2 py-1 text-[11px] font-black ${isCharterOrder(order) ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>
            {isCharterOrder(order) ? "包车" : "接送机"}
          </span>
        </div>
        <div className="mt-2 truncate text-base font-black text-slate-950">{agencyCalendarOrderCode(order)}</div>
        <div className="mt-1 truncate text-xs font-semibold text-slate-500">{order.start_time || "--:--"} · {route}</div>
      </div>
      {rangeDates.map((day) => {
        const key = formatDateKey(day);
        return (
          <button
            key={key}
            type="button"
            className={`border-r border-slate-100 ${key === selectedDateKey ? "bg-blue-50/70" : "bg-white hover:bg-slate-50"}`}
            aria-label={key}
            onClick={() => onSelectDate(key)}
            onDoubleClick={() => onCreate(key)}
          />
        );
      })}
      {placement ? (
        <div
          className={`group z-10 col-start-2 row-start-1 self-center rounded-md border px-2 py-2 text-xs font-bold shadow-sm ${profile.barClass}`}
          style={{ gridColumn: `${placement.startIndex + 2} / span ${placement.span}`, minHeight: 48, margin: "0 6px" }}
          title={`${agencyCalendarOrderCode(order)}\n${dateRangeLabel(order)}\n${route}\n${profile.label}`}
          onDoubleClick={(event) => {
            event.stopPropagation();
            onEdit(order);
          }}
        >
          <div className="truncate">{order.start_time || "--:--"} {isCharterOrder(order) ? "包车" : order.order_type || "订单"}</div>
          <div className="mt-1 truncate opacity-80">{route}</div>
          <CalendarOrderTooltip order={order} />
        </div>
      ) : null}
      {markers.map((marker) => (
        <div
          key={`${marker.key}-${marker.label}`}
          className={`z-20 row-start-1 self-start justify-self-center rounded-full px-2 py-0.5 text-[10px] font-black shadow-sm ${marker.className}`}
          style={{ gridColumn: `${marker.index + 2} / span 1`, marginTop: 4 }}
          title={marker.title}
        >
          {marker.label}
        </div>
      ))}
    </div>
  );
}

function CalendarMetric({ label, value, tone = "slate" }: { label: string; value: number; tone?: "slate" | "amber" | "blue" | "rose" | "green" | "violet" | "teal" }) {
  const toneClass = {
    slate: "bg-slate-100 text-slate-700",
    amber: "bg-amber-50 text-amber-700",
    blue: "bg-blue-50 text-blue-700",
    rose: "bg-rose-50 text-rose-700",
    green: "bg-emerald-50 text-emerald-700",
    violet: "bg-violet-50 text-violet-700",
    teal: "bg-teal-50 text-teal-700",
  }[tone];
  return (
    <div className={`rounded-lg px-3 py-2 ${toneClass}`}>
      <div className="text-[11px] font-black">{label}</div>
      <div className="mt-1 text-xl font-black">{value}</div>
    </div>
  );
}

function CalendarLegend({ color, label }: { color: string; label: string }) {
  return (
    <div className="inline-flex items-center gap-2">
      <span className={`h-2 w-5 rounded-full ${color}`} />
      {label}
    </div>
  );
}

function CalendarOrderTooltip({ order }: { order: Order }) {
  const profile = agencyCalendarStatusProfile(order);
  return (
    <div className="pointer-events-none absolute left-1/2 top-full z-50 mt-2 hidden w-80 -translate-x-1/2 rounded-lg border border-slate-200 bg-white p-3 text-left text-xs text-slate-600 shadow-xl group-hover:block">
      <div className="flex items-start justify-between gap-3">
        <div className="font-black text-slate-950">{agencyCalendarOrderCode(order)}</div>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-black ${profile.badgeClass}`}>{profile.label}</span>
      </div>
      <div className="mt-2 font-semibold text-slate-700">{dateRangeLabel(order)}</div>
      <div className="mt-1">{order.pickup_location || "-"} {"->"} {order.dropoff_location || "-"}</div>
      <div className="mt-2 grid grid-cols-2 gap-2">
        <span>车型：{order.vehicle_type || "-"}</span>
        <span>客人：{order.guest_name || "-"}</span>
        <span>人数：{order.passenger_count || "-"}</span>
        <span>报价：{order.price_jpy || order.price || "-"}</span>
      </div>
      <div className="mt-2 rounded-md bg-slate-50 px-2 py-1 font-semibold text-slate-500">
        {agencyCalendarCanEdit(order) ? "双击可修改未发布订单" : "已发布/已接单订单需走变更流程"}
      </div>
    </div>
  );
}

function agencyCalendarCanEdit(order: Order) {
  const status = order.auction_status || order.dispatch_status || "";
  return !status || status === "unassigned";
}

function CalendarDraftDialog({
  draft,
  setDraft,
  isSaving,
  error,
  onSave,
  canPublish,
  isPublishing,
}: {
  draft: { mode: "create" | "edit"; order?: Order; form: Partial<Order> };
  setDraft: (value: { mode: "create" | "edit"; order?: Order; form: Partial<Order> } | null) => void;
  isSaving: boolean;
  error: unknown;
  onSave: (publish?: boolean) => void;
  canPublish: boolean;
  isPublishing: boolean;
}) {
  const form = draft.form;
  const update = (patch: Partial<Order>) => setDraft({ ...draft, form: { ...form, ...patch } });
  const errorMessage = error instanceof Error && error.message.includes("401")
    ? "401 unauthorized：旅行社登录已失效或账号不匹配，请退出门户后重新登录再保存。"
    : error instanceof Error
      ? error.message
      : "";
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 px-4">
      <div className="w-full max-w-3xl overflow-hidden rounded-xl border border-border bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <div>
            <div className="text-base font-black text-slate-950">{draft.mode === "edit" ? "修改未发布订单" : "新建订单"}</div>
            <div className="mt-1 text-xs font-semibold text-slate-500">{draft.mode === "edit" ? draft.order?.oid || draft.order?.id : "从日历空白处快速创建"}</div>
          </div>
          <Button variant="secondary" className="h-8 px-3" onClick={() => setDraft(null)}>关闭</Button>
        </div>
        <div className="grid gap-3 p-5 md:grid-cols-2">
          <Field label="开始日期" type="date" value={form.order_date || ""} onChange={(value) => update({ order_date: value, end_date: form.end_date || value })} />
          <Field label="结束日期" type="date" value={form.end_date || form.order_date || ""} onChange={(value) => update({ end_date: value })} />
          <Field label="开始时间" type="time" value={form.start_time || ""} onChange={(value) => update({ start_time: value })} />
          <Field label="结束时间" type="time" value={form.end_time || ""} onChange={(value) => update({ end_time: value })} />
          <Field label="起点" value={form.pickup_location || ""} onChange={(value) => update({ pickup_location: value })} />
          <Field label="终点" value={form.dropoff_location || ""} onChange={(value) => update({ dropoff_location: value })} />
          <Field label="车型" value={form.vehicle_type || ""} onChange={(value) => update({ vehicle_type: value })} />
          <Field label="报价 JPY" type="number" value={form.price_jpy || form.price || ""} onChange={(value) => update({ price: value ? Number(value) : undefined, price_jpy: value ? Number(value) : undefined })} />
          <Field label="客人姓名" value={form.guest_name || ""} onChange={(value) => update({ guest_name: value })} />
          <Field label="联系方式" value={form.guest_contact || ""} onChange={(value) => update({ guest_contact: value })} />
          <label className="block text-sm md:col-span-2">
            <span className="mb-1 block font-semibold text-slate-700">备注</span>
            <textarea className="min-h-20 w-full rounded-md border border-border px-3 py-2 text-sm" value={String(form.remark || "")} onChange={(event) => update({ remark: event.target.value })} />
          </label>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-5 py-4">
          <div className="text-xs font-semibold text-slate-500">
            {draft.mode === "edit" ? "只允许未发布/未派订单直接修改；已发布订单请走变更申请。" : "保存后进入未发布订单，可继续发布到订单大厅。"}
          </div>
          <div className="flex items-center gap-2">
            {errorMessage ? <span className="text-sm font-semibold text-red-600">{errorMessage}</span> : null}
            <Button variant="secondary" disabled={isSaving || isPublishing || !canPublish} onClick={() => onSave(true)}>
              <Gavel size={16} />
              {draft.mode === "edit" ? "保存并发布到大厅" : "创建并发布到大厅"}
            </Button>
            <Button disabled={isSaving || isPublishing} onClick={() => onSave(false)}>{draft.mode === "edit" ? "保存修改" : "创建订单"}</Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function parseDateKey(value?: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || "");
  if (!match) {
    return parseDateKey(today);
  }
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

function resolveCalendarDate(current: string, options: string[]) {
  if (!options.length || options.includes(current)) {
    return current;
  }
  const target = parseDateKey(current).getTime();
  return options.reduce((best, item) => {
    const bestDistance = Math.abs(parseDateKey(best).getTime() - target);
    const itemDistance = Math.abs(parseDateKey(item).getTime() - target);
    return itemDistance < bestDistance ? item : best;
  }, options[0]);
}

function addDays(date: Date, days: number) {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function formatDateKey(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function buildDateRange(start: Date, days: number) {
  return Array.from({ length: days }, (_, index) => addDays(start, index));
}

function weekdayLabel(value: Date) {
  return ["日", "一", "二", "三", "四", "五", "六"][value.getDay()] || "";
}

function dayDiff(left: Date, right: Date) {
  const dayMs = 24 * 60 * 60 * 1000;
  return Math.round((parseDateKey(formatDateKey(left)).getTime() - parseDateKey(formatDateKey(right)).getTime()) / dayMs);
}

function timeToMinutes(value?: string) {
  const match = /^(\d{1,2}):(\d{2})/.exec(value || "");
  if (!match) return null;
  const hour = Math.max(0, Math.min(23, Number(match[1])));
  const minute = Math.max(0, Math.min(59, Number(match[2])));
  return hour * 60 + minute;
}

function addHours(value: string, hours: number) {
  const minutes = timeToMinutes(value);
  if (minutes === null) return hours >= 10 ? "19:00" : "11:00";
  const next = Math.min(minutes + hours * 60, 23 * 60 + 59);
  const hour = Math.floor(next / 60);
  const minute = next % 60;
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function addDateDaysKey(value: string, days: number) {
  const date = parseDateKey(value);
  return formatDateKey(addDays(date, days));
}

function extractDateKey(value?: string) {
  const match = /^(\d{4}-\d{2}-\d{2})/.exec(value || "");
  return match?.[1] || "";
}

function orderStartKey(order: Order) {
  return extractDateKey(order.order_date) || today;
}

function orderEndKey(order: Order) {
  return extractDateKey(order.end_date) || orderStartKey(order);
}

function defaultDurationHours(order: Partial<Order>) {
  return isCharterOrder(order as Order) ? 10 : 2;
}

function defaultEndMinutes(order: Partial<Order>) {
  const start = timeToMinutes(order.start_time) ?? 9 * 60;
  return Math.min(start + defaultDurationHours(order) * 60, 23 * 60 + 59);
}

function effectiveOrderEndTime(order: Partial<Order>) {
  return order.end_time || addHours(order.start_time || "09:00", defaultDurationHours(order));
}

function orderOverlapsRange(order: Order, rangeStartKey: string, rangeEndKey: string) {
  return orderStartKey(order) <= rangeEndKey && orderEndKey(order) >= rangeStartKey;
}

function orderTouchesDate(order: Order, dateKey: string) {
  return orderStartKey(order) <= dateKey && orderEndKey(order) >= dateKey;
}

function calendarBarPlacement(order: Order, rangeStart: Date, rangeLength: number) {
  const startIndex = Math.max(0, Math.min(rangeLength - 1, dayDiff(parseDateKey(orderStartKey(order)), rangeStart)));
  const endIndex = Math.max(0, Math.min(rangeLength - 1, dayDiff(parseDateKey(orderEndKey(order)), rangeStart)));
  if (endIndex < 0 || startIndex > rangeLength - 1) return null;
  return { startIndex, span: Math.max(1, endIndex - startIndex + 1) };
}

function calendarKeyMarkers(order: Order, rangeStart: Date, rangeLength: number) {
  const markers: Array<{ key: string; label: string; title: string; className: string }> = [];
  const auctionExpiresKey = extractDateKey(order.auction_expires_at);
  if (auctionExpiresKey) {
    markers.push({ key: auctionExpiresKey, label: "截止", title: `大厅竞拍截止：${order.auction_expires_at || ""}`, className: "bg-amber-500 text-white" });
  }
  const values = [
    ...markers,
  ].filter((item, index, arr) => item.key && arr.findIndex((other) => other.key === item.key && other.label === item.label) === index);
  return values
    .map((item) => ({ ...item, index: dayDiff(parseDateKey(item.key), rangeStart) }))
    .filter((item) => item.index >= 0 && item.index < rangeLength);
}

function agencyCalendarOrderCode(order: Order) {
  const base = order.oid || agencyBaseOrderCode(order);
  const carrier = agencyCarrierOrderSegment(order);
  const driver = agencyDriverOrderSegment(order);
  return [base, carrier, driver].filter(Boolean).join("-");
}

function agencyBaseOrderCode(order: Order) {
  const source = String(order.order_note_code || "AG").trim().toUpperCase() || "AG";
  const date = orderStartKey(order).replace(/-/g, "").slice(2) || "000000";
  const serial = String(order.id || 1).padStart(4, "0");
  return `${source}${date}-${serial}`;
}

function agencyCarrierOrderSegment(order: Order) {
  if (!isClaimedOrder(order) && !order.carrier_company_code && !order.carrier_tenant_id) return "";
  const code = companyShortCode(order.carrier_company_code || order.carrier_company_name || order.carrier_tenant_id || "CC");
  const claimDate = extractDateKey(order.carrier_claimed_at) || today;
  const date = claimDate.replace(/-/g, "").slice(2);
  const serial = String(order.carrier_claim_serial || order.auction_listing_id || order.id || 1).padStart(4, "0");
  return `${code}${date}-${serial}`;
}

function agencyDriverOrderSegment(order: Order) {
  const driverName = order.driver_name || order.assigned_driver_code || "";
  if (!order.assignment_id || !driverName) return "";
  return driverNameShortCode(driverName);
}

function companyShortCode(value: unknown) {
  const raw = String(value || "").trim();
  const ascii = raw.replace(/[^0-9A-Za-z]/g, "").toUpperCase();
  if (ascii) return ascii.slice(0, 4);
  return raw.replace(/\s+/g, "").slice(0, 2).toUpperCase() || "CC";
}

function driverNameShortCode(value: unknown) {
  const raw = String(value || "").trim();
  const words = raw.split(/\s+/).filter(Boolean);
  if (words.length >= 2 && words.every((word) => /^[A-Za-z]/.test(word))) {
    return words.map((word) => word[0]).join("").toUpperCase().slice(0, 4);
  }
  const ascii = raw.replace(/[^A-Za-z]/g, "").toUpperCase();
  if (ascii) return ascii.slice(0, 4);
  return raw.replace(/\s+/g, "").slice(0, 2).toUpperCase() || "DR";
}

function agencyCalendarStatusProfile(order: Order): { key: AgencyCalendarStatus; label: string; badgeClass: string; barClass: string } {
  if (isCancelledOrder(order)) {
    return {
      key: "cancelled",
      label: "已取消",
      badgeClass: "bg-red-50 text-red-700",
      barClass: "border-red-200 bg-red-50 text-red-800",
    };
  }
  if (isCompletedOrder(order)) {
    return {
      key: "completed",
      label: "已完成",
      badgeClass: "bg-emerald-50 text-emerald-700",
      barClass: "border-emerald-200 bg-emerald-50 text-emerald-800",
    };
  }
  if (isInProgressOrder(order)) {
    return {
      key: "progress",
      label: "进行中",
      badgeClass: "bg-violet-50 text-violet-700",
      barClass: "border-violet-200 bg-violet-50 text-violet-800",
    };
  }
  if (isClaimedOrder(order)) {
    return {
      key: "claimed",
      label: "已接单",
      badgeClass: "bg-blue-50 text-blue-700",
      barClass: "border-blue-200 bg-blue-50 text-blue-800",
    };
  }
  if (isListedOrder(order)) {
    return {
      key: "published",
      label: "已发布",
      badgeClass: "bg-amber-50 text-amber-700",
      barClass: "border-amber-200 bg-amber-50 text-amber-800",
    };
  }
  if (isExpiredOrder(order)) {
    return {
      key: "expired",
      label: "流拍",
      badgeClass: "bg-zinc-100 text-zinc-700",
      barClass: "border-zinc-300 bg-zinc-100 text-zinc-700",
    };
  }
  return {
    key: "unpublished",
    label: "未发布",
    badgeClass: "bg-slate-100 text-slate-700",
    barClass: "border-slate-300 bg-slate-100 text-slate-700",
  };
}

function isListedOrder(order: Order) {
  const dispatchStatus = order.dispatch_status || "";
  const auctionStatus = order.auction_status || "";
  return ["auction_listed", "bidding"].includes(dispatchStatus) || ["listed", "bidding"].includes(auctionStatus);
}

function isClaimedOrder(order: Order) {
  const dispatchStatus = order.dispatch_status || "";
  const auctionStatus = order.auction_status || "";
  return ["auction_claimed", "claimed", "assigned"].includes(dispatchStatus) || ["claimed", "sold"].includes(auctionStatus) || Boolean(order.assignment_id);
}

function isExpiredOrder(order: Order) {
  return order.auction_status === "expired" || order.dispatch_status === "auction_expired";
}

function isInProgressOrder(order: Order) {
  const text = `${order.execution_status || ""} ${order.dispatch_status || ""}`.toLowerCase();
  return ["in_service", "departed", "arrived", "progress", "ongoing", "running", "进行"].some((key) => text.includes(key));
}

function isCancelledOrder(order: Order) {
  const text = `${order.execution_status || ""} ${order.dispatch_status || ""} ${order.auction_status || ""}`.toLowerCase();
  return text.includes("cancel");
}

function isSettlementPendingOrder(order: Order) {
  const settlementStatus = order.settlement_status || order.agency_settlement_status || "";
  return ["pending", "payment_requested", "receipt_uploaded", "unsettled"].includes(settlementStatus);
}

function isCompletedOrder(order: Order) {
  const executionStatus = order.execution_status || "";
  const settlementStatus = order.settlement_status || order.agency_settlement_status || "";
  return ["completed", "returned"].includes(executionStatus) || ["paid", "settled"].includes(settlementStatus);
}

function isCharterOrder(order: Order) {
  const text = `${order.order_type || ""} ${order.remark || ""} ${order.pickup_location || ""} ${order.dropoff_location || ""}`.toLowerCase();
  return text.includes("charter") || text.includes("包车") || text.includes("包車");
}

function isMultiDayOrder(order: Order) {
  return orderEndKey(order) > orderStartKey(order);
}

function dateRangeLabel(order: Order) {
  const start = orderStartKey(order);
  const end = orderEndKey(order);
  const endTime = effectiveOrderEndTime(order);
  if (start === end) return `${start} ${order.start_time || ""}-${endTime}`.trim();
  return `${start} ${order.start_time || ""} -> ${end} ${endTime}`.trim();
}

function OrderTable({ rows, compact = false, uploadPdfMutation, updateFlightMutation, publishMutation }: { rows: Order[]; compact?: boolean; uploadPdfMutation?: UploadPdfMutation; updateFlightMutation?: UpdateFlightMutation; publishMutation?: PublishAuctionMutation }) {
  const queryClient = useQueryClient();
  const [rowEdits, setRowEdits] = useState<Record<number, Partial<Order>>>({});
  const updateOrderMutation = useMutation({
    mutationFn: ({ orderId, payload }: { orderId: number; payload: Partial<Order> }) => api.updateAgencyPortalOrder(orderId, payload),
    onSuccess: async () => {
      setRowEdits({});
      await queryClient.invalidateQueries({ queryKey: ["agency-portal-orders"] });
    },
  });
  const updateRowEdit = (order: Order, patch: Partial<Order>) => setRowEdits((edits) => ({ ...edits, [order.id]: { ...(edits[order.id] || {}), ...patch } }));
  const rowValue = (order: Order) => ({ ...order, ...(rowEdits[order.id] || {}) });
  function quickPublish(order: Order) {
    const price = Number(order.price_jpy || order.price || order.auction_start_price_jpy || 0);
    publishMutation?.mutate({
      orderId: order.id,
      payload: { start_price_jpy: price, buyout_price_jpy: price, auction_duration_hours: 2, note: "从订单列表快速发布" },
    });
  }
  return (
    <table className={`data-table ${compact ? "min-w-[760px]" : "min-w-[1320px]"}`}>
      <thead>
        <tr>
          <th>订单号</th>
          <th>日期时间</th>
          <th>路线</th>
          <th>车型</th>
          {compact ? <th>人数/件数</th> : null}
          <th>客人</th>
          {compact ? <th>电话</th> : null}
          <th>报价</th>
          {!compact ? <th>标准行程 PDF</th> : null}
          {!compact ? <th>司机</th> : null}
          {!compact ? <th>车辆</th> : null}
          {!compact ? <th>派车</th> : null}
          {!compact ? <th>执行</th> : null}
          {!compact ? <th>结算</th> : null}
          {!compact ? <th>操作</th> : null}
        </tr>
      </thead>
      <tbody>
        {rows.map((order, index) => (
          <tr key={order.id || `${order.order_date}-${index}`}>
            <td className="font-bold text-slate-950">{order.oid || (compact ? `预览 ${index + 1}` : order.id)}</td>
            <td>
              {!compact && canDirectEditAgencyOrder(order) ? (
                <div className="grid min-w-44 gap-1">
                  <MiniInput type="date" value={rowValue(order).order_date} onChange={(value) => updateRowEdit(order, { order_date: value })} />
                  <div className="grid grid-cols-2 gap-1">
                    <MiniInput type="time" value={rowValue(order).start_time} onChange={(value) => updateRowEdit(order, { start_time: value })} />
                    <MiniInput type="time" value={rowValue(order).end_time} onChange={(value) => updateRowEdit(order, { end_time: value })} />
                  </div>
                </div>
              ) : (
                <span>{order.order_date} {order.start_time}-{order.end_time}</span>
              )}
            </td>
            <td>
              {!compact && canDirectEditAgencyOrder(order) ? (
                <div className="grid min-w-80 gap-1">
                  <MiniInput value={rowValue(order).pickup_location} onChange={(value) => updateRowEdit(order, { pickup_location: value })} />
                  <MiniInput value={rowValue(order).dropoff_location} onChange={(value) => updateRowEdit(order, { dropoff_location: value })} />
                </div>
              ) : (
                <span>{order.pickup_location || "-"} {"->"} {order.dropoff_location || "-"}</span>
              )}
            </td>
            <td>{!compact && canDirectEditAgencyOrder(order) ? <MiniInput value={rowValue(order).vehicle_type} onChange={(value) => updateRowEdit(order, { vehicle_type: value })} /> : ([order.vehicle_type, order.vehicle_color].filter(Boolean).join(" ") || "-")}</td>
            {compact ? <td>{[order.passenger_count ? `${order.passenger_count}人` : "", order.luggage_count ? `${order.luggage_count}件` : ""].filter(Boolean).join(" / ") || "-"}</td> : null}
            <td>{!compact && canDirectEditAgencyOrder(order) ? <MiniInput value={rowValue(order).guest_name} onChange={(value) => updateRowEdit(order, { guest_name: value })} /> : (order.guest_name || "-")}</td>
            {compact ? <td>{order.guest_contact || "-"}</td> : null}
            <td>{!compact && canDirectEditAgencyOrder(order) ? <MiniInput type="number" value={rowValue(order).price_jpy || rowValue(order).price} onChange={(value) => updateRowEdit(order, { price: value ? Number(value) : undefined, price_jpy: value ? Number(value) : undefined })} /> : (order.price_jpy || order.price || "-")}</td>
            {!compact ? <td><ItineraryPdfCell order={order} uploadPdfMutation={uploadPdfMutation} /></td> : null}
            {!compact ? <td>{order.driver_name || order.assigned_driver_code || "-"}</td> : null}
            {!compact ? <td>{order.plate_number || order.plate_no || order.assigned_vehicle_type || "-"}</td> : null}
            {!compact ? <td><StatusBadge status={order.dispatch_status} /></td> : null}
            {!compact ? <td><StatusBadge status={order.execution_status} /></td> : null}
            {!compact ? <td><StatusBadge status={order.settlement_status} /></td> : null}
            {!compact ? (
              <td>
                {canPublishToHall(order) ? (
                  <Button className="h-8 whitespace-nowrap px-2 text-xs" disabled={!publishMutation || publishMutation.isPending || !Number(order.price_jpy || order.price || 0)} onClick={() => quickPublish(order)}>
                    发布到大厅
                  </Button>
                ) : (
                  <span className="text-xs font-semibold text-slate-400">-</span>
                )}
                {canDirectEditAgencyOrder(order) ? (
                  <Button className="ml-1 h-8 whitespace-nowrap px-2 text-xs" variant="secondary" disabled={!rowEdits[order.id] || updateOrderMutation.isPending} onClick={() => updateOrderMutation.mutate({ orderId: order.id, payload: rowEdits[order.id] || {} })}>
                    保存修改
                  </Button>
                ) : null}
              </td>
            ) : null}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function FlightInfoCell({ order, updateFlightMutation }: { order: Order; updateFlightMutation?: UpdateFlightMutation }) {
  const [flightNumber, setFlightNumber] = useState(order.flight_number || "");
  const [flightDate, setFlightDate] = useState(order.flight_date || order.order_date || "");
  const [flightStatus, setFlightStatus] = useState(order.flight_status || "");
  const disabled = !order.id || !updateFlightMutation || updateFlightMutation.isPending;
  const payloadBase = {
    flight_number: flightNumber,
    flight_date: flightDate || order.order_date,
    flight_status: flightStatus,
    pickup_location: order.pickup_location,
    dropoff_location: order.dropoff_location,
    start_time: order.start_time,
    order_date: order.order_date,
  };
  return (
    <div className="min-w-56 space-y-2 text-xs">
      <div className="flex items-center gap-2 font-semibold text-slate-700">
        <Plane size={14} />
        <span>{order.flight_number || "未录入航班"}</span>
        {order.flight_status ? <span className="rounded-full bg-blue-50 px-2 py-0.5 text-blue-700">{order.flight_status}</span> : null}
      </div>
      <div className="text-slate-500">
        {[order.flight_airline, order.flight_terminal, order.flight_estimated_arrival || order.flight_scheduled_arrival].filter(Boolean).join(" / ") || "可查询或手动录入"}
      </div>
      <div className="grid gap-1">
        <input className="h-8 rounded-md border border-border px-2" value={flightNumber} onChange={(event) => setFlightNumber(event.target.value)} placeholder="JL123 / NH985" />
        <div className="grid grid-cols-2 gap-1">
          <input className="h-8 rounded-md border border-border px-2" type="date" value={flightDate} onChange={(event) => setFlightDate(event.target.value)} />
          <input className="h-8 rounded-md border border-border px-2" value={flightStatus} onChange={(event) => setFlightStatus(event.target.value)} placeholder="状态" />
        </div>
      </div>
      <div className="flex flex-wrap gap-1">
        <Button className="h-8 px-2 text-xs" variant="secondary" disabled={disabled || !flightNumber.trim()} onClick={() => updateFlightMutation?.mutate({ orderId: order.id, payload: { ...payloadBase, lookup: true } })}>
          查询
        </Button>
        <Button className="h-8 px-2 text-xs" variant="secondary" disabled={disabled || !flightNumber.trim()} onClick={() => updateFlightMutation?.mutate({ orderId: order.id, payload: payloadBase })}>
          保存
        </Button>
      </div>
      {order.flight_provider ? <div className="text-[11px] font-semibold text-slate-400">{order.flight_provider} · {order.flight_last_checked_at || ""}</div> : null}
    </div>
  );
}

function ItineraryPdfCell({ order, uploadPdfMutation }: { order: Order; uploadPdfMutation?: UploadPdfMutation }) {
  if (!isCharterOrder(order)) {
    return <div className="min-w-36 text-xs font-semibold text-slate-500">机场接送无需 PDF</div>;
  }
  const disabled = !order.id || !uploadPdfMutation || uploadPdfMutation.isPending;
  const buttonText = order.itinerary_pdf_name ? "更换 PDF" : "上传 PDF";
  return (
    <div className="flex min-w-44 flex-wrap items-center gap-2">
      <label className={`inline-flex h-8 items-center gap-1 rounded-md border px-2 text-xs font-bold ${disabled ? "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400" : "cursor-pointer border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100"}`}>
        <Upload size={14} />
        {buttonText}
        <input
          className="sr-only"
          type="file"
          accept="application/pdf,.pdf"
          disabled={disabled}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (order.id && file && uploadPdfMutation) uploadPdfMutation.mutate({ orderId: order.id, file });
            event.currentTarget.value = "";
          }}
        />
      </label>
      {order.itinerary_pdf_url ? (
        <a className="inline-flex h-8 items-center rounded-md border border-slate-200 px-2 text-xs font-bold text-blue-700 hover:bg-blue-50" href={apiAssetUrl(order.itinerary_pdf_url)} target="_blank" rel="noreferrer">
          查看
        </a>
      ) : null}
    </div>
  );
}

function Kpi({ title, value }: { title: string; value: number }) {
  return (
    <div className="rounded-lg border border-border bg-white p-4">
      <div className="text-xs font-semibold text-slate-500">{title}</div>
      <div className="mt-2 text-2xl font-black text-slate-950">{value}</div>
    </div>
  );
}

function DriverVehicleSummary({ order }: { order: Order }) {
  return (
    <div className="mt-3 grid gap-2 text-xs font-semibold text-slate-500">
      <div className="inline-flex items-center gap-2"><UserRound size={14} />{order.driver_name || order.assigned_driver_code || "未显示司机"}</div>
      <div className="inline-flex items-center gap-2"><CarFront size={14} />{order.plate_number || order.plate_no || order.assigned_vehicle_type || "未显示车辆"}</div>
    </div>
  );
}

function InfoBlock({ icon, title, lines }: { icon: React.ReactNode; title: string; lines: string[] }) {
  const visibleLines = lines.filter(Boolean);
  return (
    <div className="rounded-lg border border-border bg-white p-3">
      <div className="flex items-center gap-2 text-sm font-bold text-slate-950">
        {icon}
        {title}
      </div>
      <div className="mt-3 space-y-1 text-sm text-slate-600">
        {visibleLines.map((line) => <div key={line}>{line}</div>)}
      </div>
    </div>
  );
}

function apiBaseUrl() {
  return api.baseUrl;
}

function apiAssetUrl(path: string) {
  if (/^https?:\/\//i.test(path)) return path;
  return `${apiBaseUrl()}${path.startsWith("/") ? path : `/${path}`}`;
}

function driverMapUrl(order: Order) {
  const params = new URLSearchParams({
    pickup: order.pickup_location || "",
    dropoff: order.dropoff_location || "",
  });
  if (order.driver_latitude && order.driver_longitude) {
    params.set("lat", String(order.driver_latitude));
    params.set("lng", String(order.driver_longitude));
  }
  return `${apiBaseUrl()}/driver-google-map?${params.toString()}`;
}

function TabButton({ active, icon, label, onClick }: { active: boolean; icon: React.ReactNode; label: string; onClick: () => void }) {
  return (
    <button className={`inline-flex h-10 items-center gap-2 rounded-md px-3 text-sm font-bold ${active ? "bg-blue-600 text-white" : "text-slate-600 hover:bg-slate-50"}`} onClick={onClick}>
      {icon}
      {label}
    </button>
  );
}

function Field({ label, value, onChange, type = "text" }: { label: string; value: unknown; onChange: (value: string) => void; type?: string }) {
  return (
    <label className="block text-xs">
      <span className="mb-1 block font-bold text-slate-700">{label}</span>
      <input className="h-9 w-full rounded-md border border-border px-2 text-sm" type={type} value={String(value ?? "")} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function OrderTypeSelect({ label, value, onChange }: { label: string; value: unknown; onChange: (value: AgencyOrderKind) => void }) {
  return (
    <label className="block text-xs">
      <span className="mb-1 block font-bold text-slate-700">{label}</span>
      <select className="h-9 w-full rounded-md border border-border px-2 text-sm" value={toAgencyOrderKind(value)} onChange={(event) => onChange(event.target.value as AgencyOrderKind)}>
        <option value="包车">包车</option>
        <option value="接机">接机</option>
        <option value="送机">送机</option>
      </select>
    </label>
  );
}

function parseBatchOrders(text: string): BatchOrderDraft[] {
  return sourceLines(text).map((line) => parseAgencyFreeformText(line, inferAgencyOrderKindV2(line)));
}

function mergeParsedRowsWithSource(rows: Partial<Order>[], text: string, fallbackKind: AgencyOrderKind): BatchOrderDraft[] {
  const lines = sourceLines(text);
  return rows.map((row, index) => {
    const corrected = parseAgencyFreeformText(lines[index] || "", fallbackKind);
    return { ...row, ...corrected, order_type: corrected.order_type || toAgencyOrderKind(row.order_type, fallbackKind) };
  });
}

function sourceLines(text: string) {
  return text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
}

function inferAgencyOrderKind(text: string): AgencyOrderKind {
  const lower = text.toLowerCase();
  if (/(机场|空港|airport|kansai|haneda|narita|kix|itami)/i.test(lower)) return "接机";
  return "包车";
}

function inferAgencyOrderKindV2(text: string): AgencyOrderKind {
  const normalized = normalizeAgencyText(text);
  const lower = normalized.toLowerCase();
  if (/(接机|接機|到着|arrival|arrive|pickup)/i.test(normalized)) return "接机";
  if (/(送机|送機|单送|單送|出発|departure|dropoff)/i.test(normalized)) return "送机";
  const segment = compactRouteSegment(normalized);
  const airport = findAirportAlias(segment);
  if (airport) {
    const before = segment.slice(0, airport.index).trim();
    const after = segment.slice(airport.index + airport.alias.length).trim();
    if (!before && after) return "接机";
    if (before && !after) return "送机";
    if (after && !/酒店|hotel/i.test(after)) return "接机";
    return "送机";
  }
  if (/(机场|空港|airport|kansai|haneda|narita|kix|itami|関空|关西)/i.test(lower)) return "接机";
  return "包车";
}

function parseAgencyFreeformText(text: string, kind: AgencyOrderKind): Partial<Order> {
  const normalized = normalizeAgencyText(text);
  const joined = sourceLines(normalized).join(" ");
  const fields: Partial<Order> = { order_type: kind };
  const date = /(\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2})/.exec(joined)?.[1];
  if (date) {
    fields.order_date = normalizeAgencyDate(date);
    fields.end_date = fields.order_date;
  }
  const timeRange = /(\d{1,2}:\d{2})\s*[-~到至]\s*(\d{1,2}:\d{2})/.exec(joined);
  if (timeRange) {
    fields.start_time = timeRange[1];
    fields.end_time = timeRange[2];
  } else {
    fields.start_time = /(\d{1,2}:\d{2})/.exec(joined)?.[1];
  }

  const compactAirport = parseCompactAirportTransferLine(joined, kind);
  if (compactAirport) Object.assign(fields, compactAirport);

  const hotel = labeledAgencyValue(normalized, ["酒店", "hotel"]);
  const itinerary = labeledAgencyValue(normalized, ["行程", "路线", "route", "itinerary"]);
  if (hotel) fields.pickup_location = hotel;
  if (itinerary) {
    const stops = splitAgencyRoute(itinerary);
    if (stops.length) {
      if (!fields.pickup_location) fields.pickup_location = stops[0];
      fields.dropoff_location = stops[stops.length - 1];
      fields.remark = `完整路线：${stops.join(" -> ")}`;
    }
  } else {
    const route = extractInlineRoute(joined);
    const stops = splitAgencyRoute(route);
    if (stops.length >= 2) {
      fields.pickup_location = stops[0];
      fields.dropoff_location = stops[stops.length - 1];
      fields.remark = `完整路线：${stops.join(" -> ")}`;
    }
  }

  const vehicleText = labeledAgencyValue(normalized, ["车型", "车辆", "车种", "vehicle", "car"]) || joined;
  fields.vehicle_type = extractAgencyVehicle(vehicleText) || fields.vehicle_type;
  const passenger = /(\d+)\s*(?:人|名|pax)/i.exec(vehicleText) || /(\d+)\s*(?:人|名|pax)/i.exec(joined);
  const luggage = /(\d+)\s*(?:件|个行李|行李|bags?)/i.exec(vehicleText) || /(\d+)\s*(?:件|个行李|行李|bags?)/i.exec(joined);
  if (passenger) fields.passenger_count = Number(passenger[1]);
  if (luggage) fields.luggage_count = Number(luggage[1]);

  const guestText = labeledAgencyValue(normalized, ["客人", "游客", "guest", "customer"]) || /(?:客人|游客|guest|customer)\s*[:：]?\s*([^\n]+)/i.exec(normalized)?.[1] || "";
  const guest = splitAgencyNamePhone(guestText);
  if (guest.name) fields.guest_name = guest.name;
  if (guest.phone) fields.guest_contact = guest.phone;

  const guideText = labeledAgencyValue(normalized, ["导游", "guide", "ガイド"]);
  const guide = splitAgencyNamePhone(guideText);
  if (guide.name) fields.guide_name = guide.name;
  if (guide.phone) fields.guide_phone = guide.phone;
  const wechat = /(?:微信|wechat|wx)\s*[:：]?\s*([A-Za-z0-9_.-]+)/i.exec(guideText);
  const line = /(?:Line|LINE)\s*[:：]?\s*([A-Za-z0-9_.-]+)/.exec(guideText);
  const whatsapp = /(?:WhatsApp|WA)\s*[:：]?\s*([+\d][\d\s-]{6,})/i.exec(guideText);
  if (wechat) fields.guide_wechat = wechat[1];
  if (line) fields.guide_line = line[1];
  if (whatsapp) fields.guide_whatsapp = whatsapp[1].replace(/\s+/g, "");

  const price = extractAgencyPrice(normalized);
  if (price) {
    fields.price = price;
    fields.price_jpy = price;
  }
  applyAgencyDefaultDuration(fields, joined);
  return Object.fromEntries(Object.entries(fields).filter(([, value]) => value !== undefined && value !== "")) as Partial<Order>;
}

function applyAgencyDefaultDuration(fields: Partial<Order>, source: string) {
  const kind = toAgencyOrderKind(fields.order_type, inferAgencyOrderKindV2(source));
  fields.order_type = kind;
  if (fields.order_date && !fields.end_date) fields.end_date = fields.order_date;
  if (!fields.start_time) return fields;
  if (fields.end_time) return fields;
  if (kind === "包车") {
    const days = extractAgencyCharterDays(source);
    if (days > 1 && fields.order_date) {
      fields.end_date = addDateDaysKey(fields.order_date, days - 1);
      fields.end_time = "20:00";
    } else {
      fields.end_time = addHours(fields.start_time, 10);
    }
  } else {
    fields.end_time = addHours(fields.start_time, 2);
  }
  return fields;
}

function extractAgencyCharterDays(source: string) {
  const match = /(?:包车|包車)\s*([一二三四五六七八九十\d]{1,3})\s*天|([一二三四五六七八九十\d]{1,3})\s*天\s*(?:包车|包車)/.exec(source);
  const raw = match?.[1] || match?.[2] || "";
  const value = Number(raw) || chineseNumberToInt(raw);
  return Math.max(1, value || 1);
}

function chineseNumberToInt(value: string) {
  const digits: Record<string, number> = { 一: 1, 二: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9 };
  if (!value) return 0;
  if (value === "十") return 10;
  if (value.includes("十")) {
    const [left, right] = value.split("十");
    return (left ? digits[left] || 0 : 1) * 10 + (right ? digits[right] || 0 : 0);
  }
  return digits[value] || 0;
}

function normalizeAgencyText(value: string) {
  return value.replace(/\r\n/g, "\n").replace(/\r/g, "\n").replace(/[：]/g, ":").replace(/[　]/g, " ").replace(/[→＞]/g, ">").replace(/緑/g, "绿");
}

function normalizeAgencyDate(value: string) {
  const parts = value.replace(/[/.]/g, "-").split("-").map((part) => part.trim());
  const currentYear = new Date().getFullYear();
  const [year, month, day] = parts.length === 2 ? [String(currentYear), parts[0], parts[1]] : parts;
  return `${year.padStart(4, "20")}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
}

function labeledAgencyValue(text: string, labels: string[]) {
  const labelPattern = labels.map((label) => label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|");
  const match = new RegExp(`(?:^|\\n)\\s*(?:${labelPattern})\\s*[:：]\\s*([^\\n]+)`, "i").exec(text);
  return trimAgencyPunctuation(match?.[1] || "");
}

function splitAgencyRoute(value: string) {
  return value
    .split(/\s*(?:->|>|-)\s*/)
    .map(trimAgencyPunctuation)
    .filter(Boolean);
}

function extractInlineRoute(line: string) {
  const afterTime = line.replace(/^.*?\d{1,2}:\d{2}\s*/, "");
  return afterTime
    .split(/\s+\d+\s*(?:人|名|pax)/i)[0]
    .split(/\s+\d+\s*(?:件|个行李|行李|bags?)/i)[0]
    .split(/\s+(?:Hiace|Haice|Hice|Alphard|Vellfire|Toyota|Benz|Mercedes|ハイエース|アルファード|ヴェルファイア|Grandace|Coaster)\b/i)[0]
    .split(/\s*(?:[234２３４]\s*代|[七十十八二三四\d]+\s*座|海狮|海獅|阿尔法|埃尔法|威尔法)/i)[0]
    .split(/\s+(?:客人|游客|guest|customer)\b/i)[0]
    .trim();
}

function extractAgencyVehicle(value: string) {
  const normalized = normalizeAgencyVehicleType(value);
  if (normalized) return normalized;
  const match = /(Hiace|Haice|Hice|Alphard|Vellfire|Toyota\s*\w*|Benz|Mercedes|Grandace|Coaster|ハイエース|アルファード|ヴェルファイア|海狮|海獅|阿尔法|埃尔法|威尔法|[七十十八二三四\d]+\s*座|[234２３４]\s*代)/i.exec(value)?.[1]?.replace(/\s+/g, " ").trim() || "";
  return normalizeAgencyVehicleType(match) || match;
}

function normalizeAgencyVehicleType(value: string) {
  const compact = String(value || "").replace(/\s+/g, "");
  const lower = compact.toLowerCase();
  if (/(4代|四代|４代)/.test(compact)) return "四代";
  if (/(3代|三代|３代|7座|七座|７座|阿尔法|埃尔法|威尔法|アルファード|ヴェルファイア)/.test(compact)) return "A";
  if (/(alphard|vellfire)/i.test(lower)) return "A";
  if (/(10座|十座|１０座|海狮|海獅|ハイエース|グランエース)/.test(compact)) return "海狮";
  if (/(hiace|haice|hice|grandace)/i.test(lower)) return "海狮";
  if (/(18座|十八座|１８座|中巴|マイクロバス)/.test(compact)) return "18座";
  if (/(23座|二十三座|２３座|coaster)/i.test(lower)) return "Coaster";
  if (/(巴士|バス|bus)/i.test(lower)) return "巴士";
  return "";
}

function splitAgencyNamePhone(value: string) {
  const phone = /(\+?\d{2,4}[-\s]?\d{3,4}[-\s]?\d{3,4})/.exec(value)?.[1]?.replace(/\s+/g, "") || "";
  const name = value
    .replace(phone, "")
    .replace(/\s+\d{4,7}\s*$/, "")
    .replace(/(?:微信|wechat|wx|Line|LINE|WhatsApp|WA).*$/i, "")
    .replace(/^[\s:：,，;；]+|[\s:：,，;；]+$/g, "");
  return { name, phone };
}

function trimAgencyPunctuation(value: string) {
  return value.replace(/^[\s,，;；]+|[\s,，;；]+$/g, "");
}

const airportAliasList = [
  { std: "关西机场", aliases: ["关西机场", "关西空港", "関西空港", "関西国際空港", "关西", "関空", "KIX", "Kansai International Airport"] },
  { std: "神户机场", aliases: ["神户机场", "神戸空港", "神户空港", "UKB"] },
  { std: "伊丹机场", aliases: ["伊丹机场", "伊丹空港", "大阪机场", "ITM"] },
  { std: "羽田机场", aliases: ["羽田机场", "羽田空港", "HND"] },
  { std: "成田机场", aliases: ["成田机场", "成田空港", "NRT"] },
];

function toAgencyOrderKind(value: unknown, fallback: AgencyOrderKind = "包车"): AgencyOrderKind {
  const raw = String(value || "").toLowerCase();
  if (raw.includes("接机") || raw.includes("接機") || raw.includes("pickup")) return "接机";
  if (raw.includes("送机") || raw.includes("送機") || raw.includes("dropoff") || raw.includes("departure")) return "送机";
  if (raw.includes("airport") || raw.includes("空港") || raw.includes("机场")) return fallback === "包车" ? "接机" : fallback;
  if (raw.includes("charter") || raw.includes("包车") || raw.includes("包車")) return "包车";
  return fallback;
}

function compactRouteSegment(text: string) {
  const afterTime = text.replace(/^.*?\d{1,2}:\d{2}\s*/, "");
  return afterTime
    .split(/\s*(?:Hiace|Haice|Hice|Alphard|Vellfire|Toyota|Benz|Mercedes|Grandace|Coaster|ハイエース|アルファード|ヴェルファイア|海狮|海獅|阿尔法|埃尔法|威尔法|[七十十八二三四\d]+\s*座|[234２３４]\s*代)/i)[0]
    .split(/\s*绿\s*\d+/)[0]
    .split(/\s+\d{3,7}(?:\+\d{3,7})?\b/)[0]
    .trim();
}

function findAirportAlias(text: string): { std: string; alias: string; index: number } | null {
  const compact = text.replace(/\s+/g, "");
  let best: { std: string; alias: string; index: number } | null = null;
  for (const airport of airportAliasList) {
    for (const alias of airport.aliases) {
      const index = compact.toLowerCase().indexOf(alias.toLowerCase().replace(/\s+/g, ""));
      if (index >= 0 && (!best || index < best.index || alias.length > best.alias.length)) {
        best = { std: airport.std, alias, index };
      }
    }
  }
  return best;
}

function normalizeCompactPlace(value: string) {
  const clean = trimAgencyPunctuation(value.replace(/接机|接機|送机|送機|单送|單送/g, "").trim());
  if (!clean) return "";
  if (/酒店|hotel/i.test(clean)) return clean;
  const airport = findAirportAlias(clean);
  if (airport && clean.replace(/\s+/g, "").length <= airport.alias.replace(/\s+/g, "").length + 2) return airport.std;
  return airport && /机场|空港|関空|KIX|ITM|UKB|HND|NRT/i.test(clean) ? airport.std : clean;
}

function parseCompactAirportTransferLine(line: string, fallbackKind: AgencyOrderKind): Partial<Order> | null {
  const segment = compactRouteSegment(line);
  const airport = findAirportAlias(segment);
  if (!airport && !/(接机|接機|送机|送機|单送|單送)/.test(segment)) return null;

  let kind = toAgencyOrderKind(fallbackKind);
  let pickup = "";
  let dropoff = "";
  const compact = segment.replace(/\s+/g, "");

  if (/(接机|接機)/.test(compact)) {
    kind = "接机";
    const [left, right = ""] = compact.split(/接机|接機/);
    pickup = normalizeCompactPlace(left || airport?.std || "");
    dropoff = normalizeCompactPlace(right);
  } else if (/(送机|送機|单送|單送)/.test(compact)) {
    kind = "送机";
    const [left, right = ""] = compact.split(/送机|送機|单送|單送/);
    pickup = normalizeCompactPlace(left);
    dropoff = normalizeCompactPlace(right || airport?.std || "");
  } else if (airport) {
    const before = compact.slice(0, airport.index);
    const after = compact.slice(airport.index + airport.alias.replace(/\s+/g, "").length);
    kind = before ? "送机" : "接机";
    pickup = normalizeCompactPlace(before || airport.std);
    dropoff = normalizeCompactPlace(after || airport.std);
  }

  const price = extractAgencyPrice(line);
  const result: Partial<Order> = {
    order_type: kind,
    pickup_location: pickup,
    dropoff_location: dropoff,
    vehicle_type: extractAgencyVehicle(line),
  };
  if (price) {
    result.price = price;
    result.price_jpy = price;
  }
  const luggage = /(\d+)\s*(?:件|个行李|行李|bags?)/i.exec(line);
  if (luggage) result.luggage_count = Number(luggage[1]);
  if (/儿童座椅|child seat/i.test(line)) result.remark = "儿童座椅";
  return Object.fromEntries(Object.entries(result).filter(([, value]) => value !== undefined && value !== "")) as Partial<Order>;
}

function extractAgencyPrice(text: string) {
  const labeled = labeledAgencyValue(text, ["报价", "价格", "费用", "price"]);
  if (labeled) {
    const match = /(\d{3,7})/.exec(labeled.replace(/[-\s]/g, ""));
    if (match) return Number(match[1]);
  }
  const green = /(?:绿|绿色|green)\s*(\d{3,7})(?:\s*\+\s*(\d{3,7}))?/i.exec(text);
  if (green) return Number(green[2] || green[1]);
  const plusPrice = /(?<![-\d])(\d{3,7})\s*\+\s*(\d{3,7})(?![-\d])/.exec(text);
  if (plusPrice) return Number(plusPrice[2]);
  const withoutPhones = text
    .replace(/\+?\d{2,4}[-\s]?\d{3,4}[-\s]?\d{3,4}/g, " ")
    .replace(/\d{4}[-/.]\d{1,2}[-/.]\d{1,2}/g, " ")
    .replace(/\b\d{1,2}:\d{2}\b/g, " ");
  const candidates = [...withoutPhones.matchAll(/(?<![-\d])(\d{3,7})(?![-\d])/g)].map((match) => Number(match[1])).filter((value) => value >= 300 && value !== new Date().getFullYear());
  return candidates[candidates.length - 1];
}

function fileToDataUrl(file: File, pdfOnly = false): Promise<string> {
  return new Promise((resolve, reject) => {
    if (pdfOnly && file.type && file.type !== "application/pdf") {
      reject(new Error("只能上传 PDF 文件。"));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("读取 PDF 失败。"));
    reader.readAsDataURL(file);
  });
}

function isAirportTransfer(item: { order_type?: string; pickup_location?: string; dropoff_location?: string }) {
  const text = `${item.order_type || ""} ${item.pickup_location || ""} ${item.dropoff_location || ""}`.toLowerCase();
  return text.includes("接机") || text.includes("送机") || text.includes("airport") || text.includes("空港") || text.includes("机场") || text.includes("羽田") || text.includes("成田") || text.includes("kansai") || text.includes("关西") || text.includes("関空");
}

