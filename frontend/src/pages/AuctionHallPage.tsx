import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Gavel, Plane, Plus, RefreshCw, X } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { formatCurrency, shortRoute } from "@/lib/utils";
import { api } from "@/services/apiClient";
import type { AgencyOrderChangeRequest, AuctionListing, Order } from "@/types/api";

const AUCTION_DRAFT_KEY = "tourflow_auction_publish_draft";

type AuctionDraft = {
  order_ids: number[];
  orders: Order[];
};

export function saveAuctionDraft(orders: Order[]) {
  const draft: AuctionDraft = {
    order_ids: orders.map((item) => item.id),
    orders,
  };
  window.sessionStorage.setItem(AUCTION_DRAFT_KEY, JSON.stringify(draft));
}

export function AuctionHallPage() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<AuctionDraft | null>(null);
  const [startPrice, setStartPrice] = useState("");
  const [buyoutPrice, setBuyoutPrice] = useState("");
  const [duration, setDuration] = useState<1 | 2 | 4>(1);
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");

  const listings = useQuery({
    queryKey: ["auction-listings"],
    queryFn: () => api.auctionListings("listed"),
    refetchInterval: 5000,
  });
  const changeRequests = useQuery({
    queryKey: ["auction-change-requests"],
    queryFn: () => api.auctionChangeRequests("pending"),
    refetchInterval: 5000,
  });
  const carrierSettlementListings = useQuery({
    queryKey: ["auction-carrier-settlement-listings"],
    queryFn: () => api.auctionListings("all"),
    refetchInterval: 5000,
  });

  useEffect(() => {
    const raw = window.sessionStorage.getItem(AUCTION_DRAFT_KEY);
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw) as AuctionDraft;
      if (parsed.order_ids?.length) {
        setDraft(parsed);
        const total = (parsed.orders || []).reduce((sum, order) => sum + Number(order.price || 0), 0);
        if (total > 0) {
          setStartPrice(String(Math.round(total)));
          setBuyoutPrice(String(Math.round(total * 0.8)));
        }
      }
    } catch {
      window.sessionStorage.removeItem(AUCTION_DRAFT_KEY);
    }
  }, []);

  const publishMutation = useMutation({
    mutationFn: () => {
      if (!draft?.order_ids.length) throw new Error("请先从配单界面选择订单。");
      const start = Number(startPrice);
      const buyout = Number(buyoutPrice);
      if (!start || !buyout) throw new Error("请填写起拍价和一口价。");
      if (buyout > start) throw new Error("倒拍订单的一口价不能高于起拍价。");
      return api.createAuctionListing({
        order_ids: draft.order_ids,
        start_price_jpy: start,
        buyout_price_jpy: buyout,
        auction_duration_hours: duration,
        note,
      });
    },
    onSuccess: async (result) => {
      window.sessionStorage.removeItem(AUCTION_DRAFT_KEY);
      setDraft(null);
      setStartPrice("");
      setBuyoutPrice("");
      setDuration(1);
      setNote("");
      setMessage(`已发布 ${result.count || 0} 单到拍卖大厅。`);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["auction-listings"] }),
        queryClient.invalidateQueries({ queryKey: ["dispatch-unassigned"] }),
        queryClient.invalidateQueries({ queryKey: ["orders"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] }),
      ]);
    },
  });

  const reviewMutation = useMutation({
    mutationFn: ({ requestId, decision }: { requestId: number; decision: "approved" | "rejected" }) =>
      api.reviewAuctionChangeRequest(requestId, { decision }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["auction-change-requests"] }),
        queryClient.invalidateQueries({ queryKey: ["auction-listings"] }),
        queryClient.invalidateQueries({ queryKey: ["orders"] }),
        queryClient.invalidateQueries({ queryKey: ["dispatch-unassigned"] }),
      ]);
    },
  });

  const paymentRequestMutation = useMutation({
    mutationFn: ({ orderId, amount, note }: { orderId: number; amount?: number; note?: string }) => api.requestAuctionPayment(orderId, { amount_jpy: amount, note }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["auction-carrier-settlement-listings"] }),
        queryClient.invalidateQueries({ queryKey: ["auction-listings"] }),
        queryClient.invalidateQueries({ queryKey: ["orders"] }),
      ]);
    },
  });

  const paymentConfirmMutation = useMutation({
    mutationFn: ({ orderId }: { orderId: number }) => api.confirmAuctionPayment(orderId, {}),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["auction-carrier-settlement-listings"] }),
        queryClient.invalidateQueries({ queryKey: ["auction-listings"] }),
        queryClient.invalidateQueries({ queryKey: ["orders"] }),
      ]);
    },
  });

  const claimMutation = useMutation({
    mutationFn: ({ listingId, price, mode }: { listingId: number; price: number; mode: "bid" | "buyout" }) =>
      api.claimAuctionListing(listingId, {
        claim_price_jpy: price,
        buyout_price_jpy: mode === "buyout" ? price : undefined,
        note: mode === "buyout" ? "车公司一口价接单" : "车公司竞拍接单",
      }),
    onSuccess: async () => {
      setMessage("已接单，订单会进入本公司后续派车和结算流程。");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["auction-listings"] }),
        queryClient.invalidateQueries({ queryKey: ["auction-carrier-settlement-listings"] }),
        queryClient.invalidateQueries({ queryKey: ["dispatch-unassigned"] }),
        queryClient.invalidateQueries({ queryKey: ["orders"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-summary"] }),
      ]);
    },
  });

  const draftTotal = useMemo(() => (draft?.orders || []).reduce((sum, order) => sum + Number(order.price || 0), 0), [draft]);
  const airportListings = useMemo(() => (listings.data || []).filter(isAirportListing), [listings.data]);
  const charterListings = useMemo(() => (listings.data || []).filter((item) => !isAirportListing(item)), [listings.data]);

  return (
    <div className="space-y-5">
      <section className="runtime-strip">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="runtime-eyebrow">AUCTION HALL</p>
            <h2 className="runtime-title">订单拍卖大厅</h2>
            <p className="runtime-subtitle">公司把无法执行的订单发布到大厅，其他车公司后续可以报价或一口价接单。</p>
          </div>
          <Button variant="secondary" onClick={() => listings.refetch()}>
            <RefreshCw size={16} />
            刷新
          </Button>
        </div>
      </section>

      <Card className="border-amber-100 bg-amber-50/70">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Gavel size={18} className="text-amber-700" />
            <div>
              <h2 className="text-base font-bold text-slate-950">发布确认</h2>
              <p className="mt-1 text-sm text-slate-600">从配单界面选中订单后会跳到这里，填写起拍价和一口价后发布。</p>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {draft?.orders?.length ? (
            <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
              <div className="space-y-2">
                {draft.orders.map((order) => (
                  <div key={order.id} className="rounded-lg border border-amber-100 bg-white p-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="font-bold text-slate-950">{order.oid || `#${order.id}`}</p>
                        <p className="mt-1 text-sm text-slate-600">{order.order_date || "-"} {order.start_time || ""} · {shortRoute(order.pickup_location, order.dropoff_location)}</p>
                      </div>
                      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700">{formatCurrency(order.price)}</span>
                    </div>
                  </div>
                ))}
              </div>
              <div className="rounded-xl border border-amber-100 bg-white p-4">
                <div className="grid gap-3">
                  <label className="grid gap-1 text-sm font-semibold text-slate-700">
                    起拍价
                    <input className="h-11 rounded-md border border-border px-3 text-base outline-none focus:border-amber-500" value={startPrice} onChange={(event) => setStartPrice(event.target.value)} placeholder="JPY" type="number" />
                  </label>
                  <label className="grid gap-1 text-sm font-semibold text-slate-700">
                    一口价
                    <input className="h-11 rounded-md border border-border px-3 text-base outline-none focus:border-amber-500" value={buyoutPrice} onChange={(event) => setBuyoutPrice(event.target.value)} placeholder="JPY" type="number" />
                  </label>
                  <div className="grid gap-1 text-sm font-semibold text-slate-700">
                    拍卖时间
                    <div className="flex gap-2">
                      {[1, 2, 4].map((hour) => (
                        <button key={hour} className={`h-9 rounded-md px-3 text-sm font-bold ${duration === hour ? "bg-amber-600 text-white" : "bg-slate-100 text-slate-600"}`} onClick={() => setDuration(hour as 1 | 2 | 4)}>
                          {hour} 小时
                        </button>
                      ))}
                    </div>
                  </div>
                  <label className="grid gap-1 text-sm font-semibold text-slate-700">
                    发布备注
                    <textarea className="min-h-20 rounded-md border border-border px-3 py-2 outline-none focus:border-amber-500" value={note} onChange={(event) => setNote(event.target.value)} placeholder="例如：限大阪本地车队、需要中文司机等" />
                  </label>
                  <div className="rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
                    <p>选中 {draft.orders.length} 单，原订单合计 {formatCurrency(draftTotal)}。</p>
                    <p className="mt-1">发布后订单会从本公司未派车池移出，状态变为拍卖大厅中。</p>
                  </div>
                  <Button onClick={() => publishMutation.mutate()} disabled={publishMutation.isPending}>
                    <Plus size={16} />
                    确认发布
                  </Button>
                  {publishMutation.error instanceof Error ? <p className="text-sm font-semibold text-red-700">{publishMutation.error.message}</p> : null}
                </div>
              </div>
            </div>
          ) : (
            <EmptyState title="暂无待发布订单" detail="请先回到配单界面，选中订单后点击“放入拍卖大厅”。" />
          )}
        </CardContent>
      </Card>

      {message ? <div className="rounded-lg border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">{message}</div> : null}

      <CarrierRequestPanel requests={changeRequests.data || []} reviewMutation={reviewMutation} />

      <CarrierSettlementPanel
        rows={carrierSettlementListings.data || []}
        paymentRequestMutation={paymentRequestMutation}
        paymentConfirmMutation={paymentConfirmMutation}
      />

      <Card>
        <CardHeader>
          <h2 className="text-base font-bold text-slate-950">大厅订单</h2>
          <p className="mt-1 text-sm text-slate-500">当前只做发布和展示，接单/竞价/成交转单下一步接上。</p>
        </CardHeader>
        <CardContent>
          {listings.data?.length ? (
            <div className="space-y-5">
              <AuctionListingTable title="机场接送" rows={airportListings} claimMutation={claimMutation} />
              <AuctionListingTable title="包车 / 复杂行程" rows={charterListings} claimMutation={claimMutation} />
            </div>
          ) : (
            <EmptyState title="大厅暂无订单" detail="发布成功后会显示在这里。" />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function AuctionListingTable({
  title,
  rows,
  claimMutation,
}: {
  title: string;
  rows: AuctionListing[];
  claimMutation: ReturnType<typeof useMutation<{ listing: AuctionListing }, Error, { listingId: number; price: number; mode: "bid" | "buyout" }>>;
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <div className="bg-slate-50 px-3 py-2 text-sm font-bold text-slate-950">{title}</div>
      <table className="w-full min-w-[980px] border-collapse text-left text-sm">
        <thead className="bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-3 py-3">订单</th>
            <th className="px-3 py-3">时间</th>
            <th className="px-3 py-3">路线</th>
            <th className="px-3 py-3">车型</th>
            <th className="px-3 py-3">航班</th>
            <th className="px-3 py-3">行程PDF</th>
            <th className="px-3 py-3">起拍价</th>
            <th className="px-3 py-3">一口价</th>
            <th className="px-3 py-3">截止</th>
            <th className="px-3 py-3">状态</th>
            <th className="px-3 py-3">操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.length ? rows.map((item) => {
            const bidPrice = Number(item.current_bid_jpy || item.start_price_jpy || 0);
            const buyoutPrice = Number(item.buyout_price_jpy || bidPrice || 0);
            return (
              <tr key={item.id} className="border-t border-border">
                <td className="px-3 py-3 font-bold text-slate-900">
                  {item.oid || `#${item.order_id}`}
                  <div className="mt-1 text-xs font-semibold text-slate-500">{item.listing_code || "未生成发布号"}</div>
                </td>
                <td className="px-3 py-3">{item.order_date || "-"} {item.start_time || ""}</td>
                <td className="px-3 py-3">{shortRoute(item.pickup_location, item.dropoff_location)}</td>
                <td className="px-3 py-3">{item.vehicle_type || "-"}</td>
                <td className="px-3 py-3"><FlightSummary item={item} /></td>
                <td className="px-3 py-3">{item.has_itinerary_pdf ? "有 PDF" : "-"}</td>
                <td className="px-3 py-3">{formatCurrency(item.start_price_jpy)}</td>
                <td className="px-3 py-3">{formatCurrency(item.buyout_price_jpy)}</td>
                <td className="px-3 py-3">{item.expires_at || "-"}</td>
                <td className="px-3 py-3"><span className="rounded-full bg-amber-50 px-2 py-1 text-xs font-bold text-amber-700">发布中</span></td>
                <td className="px-3 py-3">
                  <div className="flex flex-wrap gap-2">
                    <Button
                      className="h-8 px-2"
                      variant="secondary"
                      disabled={claimMutation.isPending || !bidPrice}
                      onClick={() => {
                        if (window.confirm(`确认以 ${formatCurrency(bidPrice)} 竞拍接单？`)) {
                          claimMutation.mutate({ listingId: item.id, price: bidPrice, mode: "bid" });
                        }
                      }}
                    >
                      竞拍
                    </Button>
                    <Button
                      className="h-8 px-2"
                      disabled={claimMutation.isPending || !buyoutPrice}
                      onClick={() => {
                        if (window.confirm(`确认以一口价 ${formatCurrency(buyoutPrice)} 接单？`)) {
                          claimMutation.mutate({ listingId: item.id, price: buyoutPrice, mode: "buyout" });
                        }
                      }}
                    >
                      一口价
                    </Button>
                  </div>
                </td>
              </tr>
            );
          }) : <tr><td className="px-3 py-8 text-center text-slate-500" colSpan={11}>暂无订单</td></tr>}
        </tbody>
      </table>
      {claimMutation.error instanceof Error ? <div className="border-t border-border bg-red-50 px-3 py-2 text-sm font-semibold text-red-700">{claimMutation.error.message}</div> : null}
    </div>
  );
}

function FlightSummary({ item }: { item: Partial<AuctionListing & Order> }) {
  if (!item.flight_number) {
    return <span className="text-slate-400">-</span>;
  }
  const time = item.flight_estimated_arrival || item.flight_scheduled_arrival || item.flight_estimated_departure || item.flight_scheduled_departure;
  return (
    <div className="min-w-40 space-y-1 text-xs">
      <div className="inline-flex items-center gap-1 font-bold text-slate-900">
        <Plane size={14} />
        {item.flight_number}
      </div>
      <div className="text-slate-600">{item.flight_status || "待确认"}{time ? ` / ${time}` : ""}</div>
      <div className="text-slate-500">{[item.flight_airline, item.flight_terminal, item.flight_gate].filter(Boolean).join(" / ")}</div>
    </div>
  );
}

function isAirportListing(item: { order_type?: string; pickup_location?: string; dropoff_location?: string }) {
  const text = `${item.order_type || ""} ${item.pickup_location || ""} ${item.dropoff_location || ""}`.toLowerCase();
  return text.includes("airport") || text.includes("空港") || text.includes("机场") || text.includes("羽田") || text.includes("成田") || text.includes("kansai");
}

function CarrierRequestPanel({
  requests,
  reviewMutation,
}: {
  requests: AgencyOrderChangeRequest[];
  reviewMutation: ReturnType<typeof useMutation<{ request: AgencyOrderChangeRequest }, Error, { requestId: number; decision: "approved" | "rejected" }>>;
}) {
  return (
    <Card>
      <CardHeader>
        <h2 className="text-base font-bold text-slate-950">旅行社变更/撤销确认</h2>
        <p className="mt-1 text-sm text-slate-500">旅行社订单被接单或派单后，关键变更和撤销必须由车公司确认。</p>
      </CardHeader>
      <CardContent>
        {requests.length ? (
          <div className="overflow-hidden rounded-lg border border-border">
            <table className="w-full min-w-[1080px] border-collapse text-left text-sm">
              <thead className="bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-3">订单</th>
                  <th className="px-3 py-3">旅行社</th>
                  <th className="px-3 py-3">类型</th>
                  <th className="px-3 py-3">行程</th>
                  <th className="px-3 py-3">费用策略</th>
                  <th className="px-3 py-3">申请内容</th>
                  <th className="px-3 py-3">操作</th>
                </tr>
              </thead>
              <tbody>
                {requests.map((item) => (
                  <tr key={item.id} className="border-t border-border align-top">
                    <td className="px-3 py-3 font-bold text-slate-900">{item.oid || `#${item.order_id}`}</td>
                    <td className="px-3 py-3">{item.agency_name || "-"}</td>
                    <td className="px-3 py-3">{item.request_type === "cancel" ? "撤销订单" : "修改订单"}</td>
                    <td className="px-3 py-3">{item.order_date || "-"} {item.start_time || ""}<br />{shortRoute(item.pickup_location, item.dropoff_location)}</td>
                    <td className="px-3 py-3">{item.fee_percent || 0}% / {formatCurrency(item.fee_amount_jpy || 0)}<br /><span className="text-xs text-slate-500">{item.policy_message || "-"}</span></td>
                    <td className="px-3 py-3">{formatRequestChanges(item)}</td>
                    <td className="px-3 py-3">
                      <div className="flex flex-wrap gap-2">
                        <Button className="h-8 px-2" disabled={reviewMutation.isPending} onClick={() => reviewMutation.mutate({ requestId: item.id, decision: "approved" })}>
                          <Check size={14} />
                          同意
                        </Button>
                        <Button variant="secondary" className="h-8 px-2 text-red-600" disabled={reviewMutation.isPending} onClick={() => reviewMutation.mutate({ requestId: item.id, decision: "rejected" })}>
                          <X size={14} />
                          拒绝
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="暂无待确认申请" detail="旅行社提交撤销或关键字段修改后，会显示在这里。" />
        )}
      </CardContent>
    </Card>
  );
}

function CarrierSettlementPanel({
  rows,
  paymentRequestMutation,
  paymentConfirmMutation,
}: {
  rows: AuctionListing[];
  paymentRequestMutation: ReturnType<typeof useMutation<{ order: Order }, Error, { orderId: number; amount?: number; note?: string }>>;
  paymentConfirmMutation: ReturnType<typeof useMutation<{ order: Order }, Error, { orderId: number }>>;
}) {
  const settlementRows = rows.filter((item) =>
    ["claimed", "sold"].includes(item.status || "") ||
    ["payment_requested", "receipt_uploaded", "paid"].includes(item.settlement_status || item.agency_settlement_status || ""),
  );
  return (
    <Card>
      <CardHeader>
        <h2 className="text-base font-bold text-slate-950">车公司结算联动</h2>
        <p className="mt-1 text-sm text-slate-500">订单跑完后发起付款请求；旅行社上传回执后，车公司确认收款，本订单完成。</p>
      </CardHeader>
      <CardContent>
        {paymentRequestMutation.error instanceof Error ? <div className="mb-3 text-sm font-semibold text-red-600">{paymentRequestMutation.error.message}</div> : null}
        {paymentConfirmMutation.error instanceof Error ? <div className="mb-3 text-sm font-semibold text-red-600">{paymentConfirmMutation.error.message}</div> : null}
        {settlementRows.length ? (
          <div className="overflow-hidden rounded-lg border border-border">
            <table className="w-full min-w-[1120px] border-collapse text-left text-sm">
              <thead className="bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-3">订单</th>
                  <th className="px-3 py-3">行程</th>
                  <th className="px-3 py-3">成交/请求金额</th>
                  <th className="px-3 py-3">结算状态</th>
                  <th className="px-3 py-3">旅行社回执</th>
                  <th className="px-3 py-3">操作</th>
                </tr>
              </thead>
              <tbody>
                {settlementRows.map((item) => {
                  const settlement = item.settlement_status || item.agency_settlement_status || "pending";
                  const amount = item.payment_amount_jpy || item.current_bid_jpy || item.buyout_price_jpy || item.price_jpy || item.price || 0;
                  const canRequest = !["payment_requested", "receipt_uploaded", "paid", "settled"].includes(settlement);
                  const canConfirm = settlement === "receipt_uploaded";
                  return (
                    <tr key={`${item.id}-${item.order_id}`} className="border-t border-border align-top">
                      <td className="px-3 py-3 font-bold text-slate-900">{item.oid || `#${item.order_id}`}</td>
                      <td className="px-3 py-3">
                        {item.order_date || "-"} {item.start_time || ""}<br />
                        {shortRoute(item.pickup_location, item.dropoff_location)}
                        <div className="mt-2"><FlightSummary item={item} /></div>
                      </td>
                      <td className="px-3 py-3">{formatCurrency(amount)}</td>
                      <td className="px-3 py-3"><StatusText status={settlement} /></td>
                      <td className="px-3 py-3">
                        {item.agency_payment_receipt_name || "-"}
                        {item.agency_payment_receipt_url ? <a className="ml-2 text-blue-700 hover:underline" href={assetUrl(item.agency_payment_receipt_url)} target="_blank" rel="noreferrer">查看</a> : null}
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex flex-wrap gap-2">
                          <Button className="h-8 px-2" disabled={!canRequest || paymentRequestMutation.isPending} onClick={() => paymentRequestMutation.mutate({ orderId: item.order_id, amount, note: "车公司完成订单，发起付款请求" })}>
                            发起付款请求
                          </Button>
                          <Button className="h-8 px-2" variant="secondary" disabled={!canConfirm || paymentConfirmMutation.isPending} onClick={() => paymentConfirmMutation.mutate({ orderId: item.order_id })}>
                            <Check size={14} />
                            确认收款
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="暂无待结算订单" detail="接单并完成服务后，订单会进入车公司结算联动区。" />
        )}
      </CardContent>
    </Card>
  );
}

function StatusText({ status }: { status?: string }) {
  const labels: Record<string, string> = {
    pending: "待发起付款",
    payment_requested: "待旅行社付款",
    receipt_uploaded: "待车公司确认",
    paid: "已收款完成",
    settled: "已结算",
  };
  return <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-bold text-slate-700">{labels[status || "pending"] || status}</span>;
}

function assetUrl(path: string) {
  if (/^https?:\/\//i.test(path)) return path;
  return `${api.baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
}

function formatRequestChanges(item: AgencyOrderChangeRequest) {
  if (item.request_type === "cancel") return item.reason || "申请撤销订单";
  const changes = item.requested_changes || {};
  const parts = Object.entries(changes)
    .filter(([, value]) => value !== undefined && value !== "")
    .map(([key, value]) => `${fieldLabel(key)}=${value}`);
  return parts.length ? parts.join(" / ") : item.reason || "-";
}

function fieldLabel(key: string) {
  const labels: Record<string, string> = {
    order_date: "日期",
    start_time: "开始",
    end_time: "结束",
    pickup_location: "起点",
    dropoff_location: "终点",
    vehicle_type: "车型",
    price: "报价",
    price_jpy: "报价",
  };
  return labels[key] || key;
}
