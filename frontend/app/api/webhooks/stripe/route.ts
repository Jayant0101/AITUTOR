import { createClient } from '@/lib/supabase/server';
import { logError, logInfo } from '@/lib/logger';
import { trackEvent } from '@/lib/analytics/tracker';

/**
 * Stripe Webhook Handler — Integrates SaaS subscriptions with Supabase profiles.
 * Listens for checkout completion and subscription lifecycle events.
 */
export async function POST(req: Request) {
  try {
    const payload = await req.json();
    const event = payload.type;

    logInfo(`Stripe Webhook Received: ${event}`, "STRIPE_WEBHOOK");

    const supabase = await createClient();

    switch (event) {
      case 'checkout.session.completed':
        const session = payload.data.object;
        const userId = session.client_reference_id;
        const plan = session.metadata.plan || 'pro';
        const customerId = session.customer;
        const subscriptionId = session.subscription;

        if (userId) {
          const { error } = await supabase
            .from('profiles')
            .update({ 
              subscription_tier: plan,
              billing_status: 'active',
              stripe_customer_id: customerId,
              stripe_subscription_id: subscriptionId,
              updated_at: new Date().toISOString()
            })
            .eq('id', userId);
          
          if (error) throw error;
          await trackEvent('subscription_started', { user_id: userId, plan });
        }
        break;

      case 'invoice.payment_failed':
        const failedInvoice = payload.data.object;
        const failedSubId = failedInvoice.subscription;
        
        await supabase
          .from('profiles')
          .update({ billing_status: 'past_due' })
          .eq('stripe_subscription_id', failedSubId);
          
        logError(`Payment failed for subscription ${failedSubId}`, "STRIPE_BILLING");
        break;

      case 'customer.subscription.deleted':
        const deletedSub = payload.data.object;
        await supabase
          .from('profiles')
          .update({ 
            subscription_tier: 'free', 
            billing_status: 'canceled' 
          })
          .eq('stripe_subscription_id', deletedSub.id);
        break;

      default:
        logInfo(`Unhandled event type ${event}`, "STRIPE_WEBHOOK");
    }

    return Response.json({ received: true });
  } catch (error) {
    logError(error, "STRIPE_WEBHOOK_ROUTE");
    return Response.json({ error: "Webhook handler failed" }, { status: 500 });
  }
}
