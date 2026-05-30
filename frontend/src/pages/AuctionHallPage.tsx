import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Gavel, Plus, RefreshCw } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { formatCurrency, shortRoute } from "@/lib/utils";
import { api } from "@/services/apiClient";
import type { Order } from "@/types/api";

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
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");

  const listings = useQuery({
    queryKey: ["auction-listings"],
    queryFn: () => api.auctionListings("listed"),
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
          setStartPrice(String(Math.round(total * 0.8)));
          setBuyoutPrice(String(Math.round(total)));
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
      if (buyout < start) throw new Error("一口价不能低于起拍价。");
      return api.createAuctionListing({
        order_ids: draft.order_ids,
        start_price_jpy: start,
        buyout_price_jpy: buyout,
        note,
      });
    },
    onSuccess: async (result) => {
      window.sessionStorage.removeItem(AUCTION_DRAFT_KEY);
      setDraft(null);
      setStartPrice("");
      setBuyoutPrice("");
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

  const draftTotal = useMemo(() => (draft?.orders || []).reduce((sum, order) => sum + Number(order.price || 0), 0), [draft]);

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

      <Card>
        <CardHeader>
          <h2 className="text-base font-bold text-slate-950">大厅订单</h2>
          <p className="mt-1 text-sm text-slate-500">当前只做发布和展示，接单/竞价/成交转单下一步接上。</p>
        </CardHeader>
        <CardContent>
          {listings.data?.length ? (
            <div className="overflow-hidden rounded-lg border border-border">
              <table className="w-full min-w-[980px] border-collapse text-left text-sm">
                <thead className="bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-3">订单</th>
                    <th className="px-3 py-3">时间</th>
                    <th className="px-3 py-3">路线</th>
                    <th className="px-3 py-3">发布公司</th>
                    <th className="px-3 py-3">起拍价</th>
                    <th className="px-3 py-3">一口价</th>
                    <th className="px-3 py-3">状态</th>
                  </tr>
                </thead>
                <tbody>
                  {listings.data.map((item) => (
                    <tr key={item.id} className="border-t border-border">
                      <td className="px-3 py-3 font-bold text-slate-900">{item.oid || `#${item.order_id}`}</td>
                      <td className="px-3 py-3">{item.order_date || "-"} {item.start_time || ""}</td>
                      <td className="px-3 py-3">{shortRoute(item.pickup_location, item.dropoff_location)}</td>
                      <td className="px-3 py-3">{item.seller_company_name || item.seller_company_code || "-"}</td>
                      <td className="px-3 py-3">{formatCurrency(item.start_price_jpy)}</td>
                      <td className="px-3 py-3">{formatCurrency(item.buyout_price_jpy)}</td>
                      <td className="px-3 py-3"><span className="rounded-full bg-amber-50 px-2 py-1 text-xs font-bold text-amber-700">发布中</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title="大厅暂无订单" detail="发布成功后会显示在这里。" />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
